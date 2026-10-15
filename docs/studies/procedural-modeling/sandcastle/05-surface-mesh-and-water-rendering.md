# 模型：规则网格怎样变成沙面与水面

本轮已把**生成平面网格 → 计算高度场 → 顶点读取高度 → 水体薄层裁掉**连起来。沙堡主地表的丰富外形来自固定拓扑上的高度变化；这条路径没有为每颗沙生成模型，也没有使用三维体素等值面重建。对包内其他道具不作这个概括。

## CPU 先生成拓扑

按[CPU 调查](03-excavation-and-mesh.md)，`Ground.Setup`（首选 VA `0x180450d78` 附近的调用）调用 `PlaneGenerator.Generate`（`0x180493db0`）。`Generate(resolution,size,name)` 为分辨率 `(rx,ry)` 分配 `(rx+1)×(ry+1)` 个顶点和 `rx×ry×6` 个索引；Ground.Setup 的循环准备四个 planeChunks。每格两三角形，顶点 XZ 由网格和尺寸决定。MeshCollider 则有自己的更新路径，不能把显示顶点位移自动视为物理碰撞已经同步。

**构造演算。** 若某块平面分辨率为 `(2,2)`，生成 9 个顶点、24 个索引，即 8 个三角形。修改中间顶点对应的高度状态，仍可沿用这些三角形索引。`(2,2)` 是演算输入，实际地图/块分辨率未从序列化实例全部确认。

## GPU 怎样把沙面抬起来

实际读取 `sharedassets0.assets` 内的 Shader 对象：

| Shader    | pathID | 对象文件偏移/长度      | 压缩表相对偏移 | LZ4 段：压缩→展开 |
| --------- | -----: | ---------------------- | -------------- | ----------------- |
| Lit/Sand  |    605 | `0x2fc0e80` / 21,688 B | `0x31ec`       | 8,814→98,128 B    |
| Lit/Water |    587 | `0x2f34df0` / 7,364 B  | `0xfec`        | 3,196→17,648 B    |

对象中的实际 Shader 名称分别出现在 `0x2fc4050` 与 `0x2f35dbc`。来源身份同[GPU 模拟报告](04-gpu-simulation-and-brush.md)。[读取探针](../tools/unity22-shader-probe.py)从人工确认的表偏移读取平台、范围与大小，严格检查 LZ4 展开长度和 DXBC chunk 边界。此处没有恢复完整 Shader 序列化 schema，也没有推定所有 pass 的真实执行顺序。

Lit/Sand 解出 32 个、Lit/Water 解出 4 个 DXBC 记录，均由 Windows API 反汇编。它们包含变体与不同 pass，不能称为 36 个独立生成算法。输出和偏移账本位于 `.cache/procedural-modeling/sandcastle/graphics/`。

`shader-605-0-01.asm.txt` 的首顶点程序直接确认：

1. 指令 3–8：将输入顶点经物体矩阵得到世界 XZ，除以 `beachSize.xz` 再加 0.5，夹到 `[0,1]`。
2. 指令 9–14：映射到 `uv×groundResolution−0.5`，夹到合法格范围，取整为整数索引，读 16 B 地表状态。
3. 指令 15–20：从第三/第四个 uint 拼出 24 bit 高度，乘浮点位模式 `0x3521999b`，约为 `10.1/(2²⁴−1)`。
4. 指令 21–25：将这个高度作为世界 Y，与世界 XZ 一起进入观察投影变换，写 `SV_POSITION`。

这几步给出实际可见几何的来源。该顶点变体取一个地表格高度；不能把另一路双线性取水格的处理移植成“沙面顶点总是双线性”。法线、速度与湿润相关通道也从打包状态解出，传给片元程序。

**构造演算。** 若取出的高度编码 `H24≈0.8×(2²⁴−1)/10.1`，当前顶点世界 Y 约 0.8；笔刷把对应格高度改为约 0.85，下一次消费新缓冲时同一拓扑顶点抬高约 0.05。这里展示已确认的数据流，不建立 CPU/GPU 同步延迟为一帧或可忽略。

主地表这一路每个 XZ 对应一个高度，因而该表示本身不能描述同一 XZ 上有多个实体表面的悬挑、洞穴内腔。精细工具造成的陡边可以由高分辨率高度突变表达；不能仅凭画面有竖墙就判断用了体素布尔。

## 水面不是覆盖全图的平色片

`shader-587-0-01.asm.txt` 读取水格与地表格两种 buffer。顶点程序指令 13–60 从四邻取水底高度和水量，对每个样本形成：

`sampleSurface = floorHeight + max(waterAmount−0.05, 0)`

再以四样本算术平均值形成当前顶点 Y，送入观察投影变换。`0.05` 是这条显示/模拟约定里的明确偏移，不能忽略后把 waterAmount 直接叫可见水深。

顶点另将当前采样的 `max(waterAmount−0.05,0)` 传给片元阶段；`shader-587-0-03.asm.txt` 指令 0–2 在它小于约 `1e−5` 时 discard。水量不够的地方，水面三角形的对应片元不绘制。后续还有法线、纹理和光照操作；完整反射、透明混合与所有材质参数未逐项恢复。

**构造演算。** 四个邻样本的水底均为 0.2，waterAmount 均为 0.35，四样本表面都是 `0.2+(0.35−0.05)=0.5`，顶点高度即 0.5。若当前用于覆盖判断的水量为 0.04，有效水量为 0，该片元被丢弃。这是 shader 局部规则演算；边界处的插值、三角覆盖和相机结果需实际渲染验证。

## 与 Tiny Glade 的区别和可借鉴处

Tiny Glade 的[水体调查](../07-tiny-glade-water-shape-and-banks.md)已有笔画、栅格与河床/岸边链；本轮沙堡进一步确认会持续演化的水速、沙速、悬沙和侵蚀沉积。共同点是把编辑状态与最终显示分开，区别在于沙堡本轮已查到随时间更新地形的模拟驱动。

独立开发时，可借鉴这种分工：固定网格负责拓扑，格网状态负责外形，工具修改状态，模拟继续推进，碰撞采用明确的读回/更新策略。要自行选择分辨率、更新频率、格式精度与边界条件；本次没有在 Unity 自研工程中实现或接受这些选择，也不把恢复 shader 当作可分发代码。

## 复现入口和验证范围

在仓库根使用当前安装路径：

```powershell
python docs/studies/procedural-modeling/tools/unity22-shader-probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --object-id 605 --table-offset 0x31ec --output .cache/procedural-modeling/sandcastle/graphics
python docs/studies/procedural-modeling/tools/unity22-shader-probe.py "C:/Software/Steam/steamapps/common/Sandcastle Demo/Sandcastle_Data/sharedassets0.assets" --object-id 587 --table-offset 0xfec --output .cache/procedural-modeling/sandcastle/graphics
```

已验证：两个段均按声明长度展开；36 个 DXBC 的边界与 Windows 反汇编成功；所述顶点高度和薄水层裁剪有原始操作数。Not Run：真实游戏、交互截图、GPU 帧捕获、物理碰撞一致性、全地图/全 pass 的视觉等价验证。Shader 表布局参考 [AssetStudio 固定版本的 Shader 读取实现](https://github.com/Perfare/AssetStudio/blob/d158e864b556b5970709c2a52e47944d53aa98a2/AssetStudio/Classes/Shader.cs)，使用它理解压缩表，不以旧引擎读取器的能力宣称完整支持 Unity 6。
