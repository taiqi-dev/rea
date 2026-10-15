# SUMMERHOUSE：TAA 历史目标的生命周期与关闭条件

[16](16-additional-camera-layout-and-effect-gates.md)已确认两台相机序列化的 AA 模式均为 None，并保留“维护 TAA 数据不等于分配历史纹理”的边界。本篇接通两者：**`Init` 更新描述符并按条件释放旧目标，真正分配发生在独立 `AllocateTargets`；普通相机渲染中的 TAA 启用门为 false 时会调用 `DeallocateTargets`。** 在16的配置已被消费且未被改写的条件下，两台相机走关闭分支，不能由保存的 TAA 参数推断分配了历史纹理；CPU 对象、检查和状态更新仍可能存在。没有测量实际内存或帧时。

## 所有者与普通渲染入口

沿用同版 `C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data\Managed\Unity.RenderPipelines.Universal.Runtime.dll`（644608 B，MVID `441516f4-c7ab-401e-840b-a71a7013b536`）和16的资源身份，不重算目标摘要。本轮用既有[离线 CIL 读取器](tools/ManagedCilProbe/Program.cs)，只解析 PE metadata／方法体，不加载目标执行。

`UniversalAdditionalCameraData..ctor 0x06000756 / IL_006C…0072` 创建 `TaaPersistentData` 并存入非序列化字段 `m_TaaPersistentData`；其 getter `0x0600073F / IL_0001` 只返回字段，不是 lazy 分配函数。`TaaPersistentData..ctor 0x060006C5` 自身仅调用 Object 构造器，没有 RTHandles 分配。因此“追加数据存在一个 TAA 状态对象”与“存在 GPU 历史目标”是两件事，构造调用是否实际发生仍为运行条件。

[16](16-additional-camera-layout-and-effect-gates.md)已追的 `UpdateTemporalAAData 0x0600080F` 把该对象和 Settings 写入 CameraData，并调用其 `Init`。普通入口 `UniversalRenderPipeline.RenderSingleCamera 0x060007FF / IL_019D…01A6` 在 CameraData 的 persistent data 非空时，进一步调用 `UpdateTemporalAATargets 0x06000810`；随后才设置 RTHandles 参考尺寸并进行该处的 Cull／RenderingData 初始化。本篇只连接这条托管普通渲染路径，未借此证明原生相机列表准入、截图入口或每显示帧执行次数。

## Init 的缓存判定与失效范围

`TaaPersistentData.Init 0x060006C6` 长229 B。`IL_0000…0030` 先依次比较旧 descriptor 的 width、height、volumeDepth；三者相同且第一张 accumulation target 非空时，直接跳 `IL_00E4` 返回。否则在输入宽高均大于零时创建新的 descriptor：MSAA=1、depth=0、sRGB=false、useMipMap=false、autoGenerateMips=false、randomWrite=false、dynamicScale=false；图形格式经该类的 CheckFormat helper 处理，未把设备支持结果当成本机已观测值。`IL_00D7…00DF` 保存 descriptor 后调用 `DeallocateTargets`，没有调用 `RTHandles.Alloc`。

这个 early-return 判定只显式比较上述三个尺寸和第一目标是否存在，未比较这次传入的 graphicsFormat、dimension、vrUsage。构造例：旧目标存在，宽高和volumeDepth都相同，但构造输入把格式改为另一个值，该局部判定仍直接返回；这说明该方法的缓存键边界，**不证明游戏实际会在这里改变格式或产生错误**。输入宽高非正时也在此方法直接返回，不能概括成“任何参数变化都会释放历史目标”。

## 分配、关闭与销毁

| 方法与位置                                                          | 静态状态转移                                                                                                                             | 不能据此声称                                     |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `UpdateTemporalAATargets 0x06000810 / IL_0000…0006`                 | 先调用 CameraData.IsTemporalAAEnabled；false 跳至 `IL_004E`。该启用门按16首先要求 AA==3。                                                | 不由TAA Settings的quality=3推断模式为TAA。       |
| 同方法 `IL_0029…0030`                                               | true 分支调用 persistent data 的 AllocateTargets；第二目标布尔参数来自 XR enabled 且非single-pass的组合。                                | 不推断本机实际XR状态。                           |
| `AllocateTargets 0x060006C7 / IL_0002…0058`                         | 第一目标空才用 RTHandles.Alloc 建 `_TaaAccumulationTex`；参数为true且第二目标空，才建 `_TaaAccumulationTex2`。返回本次是否创建任一目标。 | 不等于每帧重新分配，也不提供实际显存字节数。     |
| `UpdateTemporalAATargets / IL_0035…004C`                            | 仅在分配函数返回true时，将 CameraData Settings 的 resetHistoryFrames 加1或2。                                                            | 不等于任何Init或任何显示帧都增加该计数。         |
| 同方法 `IL_004E…0054`                                               | 启用门false，调用 DeallocateTargets。                                                                                                    | 不代表完全没有CPU对象或分支成本。                |
| `DeallocateTargets 0x060006C8 / IL_0000…003E`                       | 两目标非空才各调用Release，随后将两引用置null、两个最后累积帧索引置-1。                                                                  | 没有运行证据证明底层GPU释放时间或失败后的行为。  |
| `UniversalAdditionalCameraData.OnDestroy 0x06000755 / IL_002B…0036` | 正常走到该段且persistent data非空时，调用同一DeallocateTargets；前面另有volume／renderer清理。                                           | 不从方法存在证明实际调用、正常到达或异常时保证。 |

对本作配置的演算：假设相机以16读出的 AA=None 初始化到 CameraData，persistent data 非空，且本轮所查门前没有覆盖；RenderSingleCamera进入UpdateTemporalAATargets后，IsTemporalAAEnabled第一条件返回false，选择释放／清空分支，**不会沿此入口调用AllocateTargets**。若旧目标本已为空，则该释放方法跳过两次Release，仍写null及-1。这是条件指令演算，不是一次帧观察或内存测量。

`TemporalAA.CalculateJitterMatrix 0x060006CC / IL_0000…000C` 也从单位矩阵开始，启用门false即跳到返回。因此在同样前提下该方法返回单位矩阵；不能从它推断完整相机投影没有其它变化。

## 覆盖与复算

新 raw 位于 ignored `.cache/procedural-modeling/static-bufferstate-followup/summerhouse/`：`taa-persistent-data.json`（此类11个方法）、`taa-persistent-getter.json`、`taa-owner-creation.json`、`taa-owner-cleanup.json`、`taa-jitter-gate.json`、`taa-target-update-entry.json`，以及 `taa-allocation-consumers.json` 和 `taa-allocation-all-callers.json`。先查UniversalRenderer没有命中，随后对本DLL的492个TypeDef、2520个MethodDef检查 resolved operand；2509个有体方法已解码，11个无方法体。后一范围只找到上述UpdateTemporalAATargets这一直接调用者。它不排除反射、外部程序集、间接调用或原生代码。

可用同一正式工具复读完整TAA状态类（输出须为新路径）：

```powershell
dotnet .cache/procedural-modeling/static-chain-followup/summerhouse/managed-bin/net9.0/ManagedCilProbe.dll 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/Managed/Unity.RenderPipelines.Universal.Runtime.dll' UnityEngine.Rendering.Universal.TaaPersistentData '*' .cache/procedural-modeling/static-bufferstate-followup/summerhouse/taa-persistent-recheck.json
```

其它输出的精确类型、方法筛选与operand筛选保留在各JSON的type／coverage及方法token中。均是普通静态输出，没有新REA Evidence；Ghidra既有阻塞未变，未重试。**Answered（静态条件）：** CPU对象所有权、Init与分配分离、普通入口的分配／关闭门、销毁正常路径和jitter门。**Partial：** 实际相机准入、动态覆盖、其它入口、GPU释放和真实成本。**Not Run：** 游戏、目标代码、相机/GPU、截图、像素和性能测量。
