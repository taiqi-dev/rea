# 挖掘、堆积与规则地表模型

## 画刷是共同输入

`Brush` 的 metadata 字段有 `operation`、`mode`、`localToWorld`、`velocity`、`wrap`、`shape`、`easing`、`patternStencil`；`Brush.SetComputeShaderValues` (`0x18043ED30`) 将这些配置传到计算着色器。枚举的字段默认值与原生立即数交叉确认如下：`Operation` 0=Add、1=Sub、2=Blend、3=Stamp、4=Smooth、5=Fill、6=Push、7=Min、8=Max、9=Smear、10=StampMax；`Mode` 0=Default、1=Stencil。名称来自 metadata，实际数值还由 `field_defaults` 的单字节压缩值验证；例如 `Push` 的值为 6，而 `Shovel.OnAction` 在 `0x180478EE0` 与 `0x18047934A` 写入 `Brush.operation=6`。枚举名称不是公式；各值的 GPU 行为见 [画刷计算着色器分析](04-gpu-simulation-and-brush.md)。

`Beach.Raze(pattern)` (`0x180427EA0`) 先构造 Brush，再转给接收 Brush 的重载 (`0x180427F60`)；后者写入 operation=2、mode=1，并清理 Dirt、Gravel、Plants 粒子相关层。`Beach.Wet` 的类似重载 (`0x180428780`) 将 mode=1 的刷子传入 Water。由此可见，地面编辑不只改高度，也可能触发水与可见碎屑层的联动；尚不能把每种效果归因于某个未追到的 Unity 内部函数。

## 铲子的两类路径

**观察**：`Shovel.OnAction` (`0x180478B20`，本地有界指令覆盖至 `0x180479650`) 先检查工具激活/可用条件，计算命中与刷子变换。它构造 `Push` 刷子，调用 `Brush.VolumeApproximation` (`0x18043F360`) 求影响体积，再经 `Ground.UpdateTangent` (`0x180451650`) 和 Beach 的 `Raze` / `Impact` 更新相邻表现。一个分支在输入刷子数据中反转沙量符号 (`0x180478F08–0x180478F35`)，对应从地面挖取/移走；另一分支把沙量作为正值用于回填/推动 (`0x180479379–0x1804793C1`)。后一个分支会检查剩余水量阈值，再构造水相关刷子并触发 `Water.UpdateTangent` (`0x1804793E7–0x1804794C2`)。分支的精确触发输入来自 24 字节 action 结构，目前只能确认其不同 flag 分流，未还原按键时序。

若命中的是 `Bucket`，铲子路径调用 `Bucket.IncrementSand` (`0x18043F4B0`) 和 `Bucket.IncrementWater` (`0x18043F590`)；若命中其他对象，则沿 Ground/Water 刷子分支。元数据还有 `Shovel.sandCapacity`、`collectedWater` 与 `Bucket.sandCapacity/waterCapacity/sand/water` 等字段，支持“挖取量与容器库存耦合”的状态结构。**未证实**每次挖取的量必然完全守恒，也未从静态文件得到默认容量。可复查 `disasm/Shovel_OnAction_full.txt`、`Bucket_IncrementSand_8b.txt`、`Bucket_IncrementWater_8a.txt`。

`Mold.Stamp` (`0x18045B320`) 是另一条堆积路径：根据模具选项构造 Brush 并提交地面绘制；`wet`、`raze` 条件分别调用 `Beach.Wet` (`0x180428780`) 与 `Beach.Raze` (`0x180427F60`)，之后调用 `Beach.Impact` (`0x1804278F0`)。这解释了压模时“改高度 + 处理含水/覆盖物 + 反馈”可以由同一输入串联，而非以模型顶点直接塑形。模具实际目标高度、纹理阈值与融合公式由 GPU 证据限定，详见 [04](04-gpu-simulation-and-brush.md)。

**构造算例**：在沙地上给一个局部圆形 Brush 施加负量，CPU 形成变换/影响体积并向 Ground 提交；沙状态随后由计算着色器改写，下一次渲染用高度状态抬降规则网格顶点。若工具判定命中 Bucket，则另更新库存。此例是已观察调用关系的说明；没有把具体“每铲减少几厘米”写成未知参数的假数。

## 网格拓扑、碰撞和可见高度

`PlaneGenerator.Generate(resolution, size, name)` 的三个参数名来自 metadata，入口 `0x180493DB0`。原生指令先分配 `(rx+1)×(ry+1)` 个顶点/法线/UV 与 `6×rx×ry` 个三角索引 (`0x180493E17–0x180493EC6`)，随后按双重循环以 `size` 计算规则平面坐标与 UV (`0x180493FB0–0x1804940D7`)，对每格写六个索引 (`0x1804940FE–0x1804941A7`)；索引数组超过 `0x7FFF` 时选择宽索引格式 (`0x180493F15`)。`Ground.Setup` 于 `0x180450D78` 调此方法，循环产生四个 `planeChunks`。这里“4”是该 CPU 初始化路径的观察值；不同 LOD 或海滩配置是否另有覆盖，尚未验证。

`Ground.Run` 在适当 step 取一个 `planeChunk` 调 `UpdateMeshCollider` (`0x1804506AF–0x1804506F6`)，并将轮询索引模数组长度递增。`PlaneChunk.UpdateMeshCollider` (`0x18045F120`) 读取相关网格数据后逐顶点更新碰撞用 Mesh，再同步 `MeshCollider` (`disasm/PlaneChunk_UpdateMeshCollider_216.txt`)；因而交互碰撞与高频 GPU 可见形变并非同一更新频率。最终沙/水的**可见模型**如何从高度状态形成，需结合 [顶点/像素着色器分析](05-surface-mesh-and-water-rendering.md)：当前实证显示沙顶点按世界 XZ 采样 ground 高度作 Y 位移，水顶点从邻域 floor/amount 构成水面。它是规则拓扑上的高度位移，不能解释为每颗沙粒各有一个模型，也无证据支持体素 Marching Cubes。

尚未确认序列化 `Layer.resolution`、碰撞分辨率的默认具体数值，因此这里仅给参数化的顶点/三角数量公式。网格几何尺寸、默认高度比例以及局部 Brush 与世界坐标变换应以相应海滩资产和 GPU 常量再核对。
