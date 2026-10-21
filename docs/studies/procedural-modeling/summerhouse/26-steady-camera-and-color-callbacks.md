# SUMMERHOUSE：稳态相机循环与配色回调的不同频率

这次续查把 [22 的像素网格与相机位移](22-pixel-grid-camera-motion-and-silhouette-stability.md)、[19–20 的调色板写端与分类曲线](19-palette-propagation-and-shared-state.md) 和 [25 的反射回调](25-reflection-texture-lifecycle-and-binding.md) 放在同一条稳态时间线上。**静态实现可见：相机的正常 `Update` 会尝试输入、移动、缩放；没有移动输入也会进入地面射线与位置限制。配色管理器没有自己的 `Update`，颜色批量应用来自 Start／切换入口和有限时长协程。**这不说明整个游戏没有其他逐帧工作，也不是帧时或瓶颈测量。

## 身份与证据范围

目标为 `C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/Managed/Assembly-CSharp.dll`，186880 B，MVID `84569538-a19f-4c17-8ccf-f40b95e99253`，REA 本轮记录的 SHA-256 为 `f4e8bf23299a5e4a916d4bd955e108d2f3760117e5850adf10926ee6aa8379de`，沿用本次调查授权。REA `inspect_managed_members` 的 `ev_85c8f6aa9045c8ba243f94326b0355f873f6171e0352a4b1b5867904419f376d` 精确命中 `CameraController` 与 `ColorManager`（2 类型、28 方法），`ev_c8a997eff213d21c6b2b0c04949491647762472c672c25ba1a74beed5d4b7778` 精确命中裸嵌套类型 `<BlendCoroutine>d__17`（1 类型、6 方法）；两者均提供 file-backed CIL anchor。完整 [REA bundle](../../../../.cache/procedural-modeling/steady-performance-followup/summerhouse/rea-evidence-bundle-final.json) 保存在本机 ignored 目录。

同一 bundle 中的 `ev_40284d301716c46bd201890268ceb5f47c88fe2ca5933b98244ea7b7a98030da` 请求全名 `ColorManager+<BlendCoroutine>d__17`，结果为 **0 类型、0 方法**；其 metadata 扫描标为 `complete` 不能当作目标类型已覆盖。普通离线 [CameraController CIL](../../../../.cache/procedural-modeling/steady-performance-followup/summerhouse/camera-cil.json) 为 19/19 方法、[ColorManager CIL](../../../../.cache/procedural-modeling/static-state-followup/summerhouse/color-manager.json) 为 9/9、[协程 CIL](../../../../.cache/procedural-modeling/steady-performance-followup/summerhouse/blend-coroutine-cil.json) 为 6/6；它们与 REA anchor 分开标记。MethodDef token 与 IL 偏移只在上述 DLL 身份下有效。没有加载程序集或运行目标。

[22 的场景解析](../../../../.cache/procedural-modeling/static-art-followup/summerhouse/camera-grid-config.json)在发行的 `level0…4` 中只找到 `level0/6732` 一件 `CameraController`，序列化 `m_Enabled=1`；该组件与 PixelateLayer 的引用也已完整解析。这是静态可达性，不证明当时加载哪个 scene、组件是否仍启用，或运行帧确实调用了 `Update`。

## 正常 Update 有持续的输入和位置工作

`CameraController.Update 0x060000C3 / IL_0001…0053` 首先检查 `hasTeleportedThisFrame`；若真，跳过本次 `ProcessInput`、`Move`、`ZoomCamera` 和可选拖拽，随后在 `IL_004C…0052` 把标志清零。因此 `TeleportToPosition 0x060000CE` 设位后的**一次 Update** 被跳过；后续正常 Update 会恢复这三步。标志为假时，这三个调用按 `ProcessInput (IL_0009) → Move (IL_000F) → ZoomCamera (IL_0015)` 顺序发生。`DragCamera` 另受按键保持、菜单和设置／预览门约束；它不改变前三步已经发生的事实。

`ProcessInput 0x060000C8` 在菜单或 Picker 打开时跳到 `IL_007F`，把 `currentMovement` 设为零；否则读取方向输入，并在 `IL_0060…0079` 用 `Vector3.SmoothDamp` 更新移动状态。**Move 不是只在非零移动时才被 Update 调用。**`Move 0x060000C9 / IL_0000…003B` 先以当前位置上方、向下、距离 `100` 和 `groundCastLayerMask` 调 `Physics.Raycast`，丢弃布尔返回值，读取 `RaycastHit.point.y` 形成 `minHeight`；`IL_0077…0099` 随后用 `currentMovement × moveSpeed × deltaTime` 调 `Transform.Translate`，`IL_009E…00F3` 读/设位置并限制高度，最后 `IL_00F8…00F9` 调 `ApplyPositionBoundaries`。该方法在这些指令之间没有“位移为零就返回”的分支。即使方向输入为零，CIL 仍提交 Raycast、Translate 和 set_position 的调用；这些 Unity API 在零向量／相同位置时的内部实际工作量未测。Raycast 失败时的地面结果也不能从被丢弃的布尔值推定。

`ZoomCamera 0x060000C4 / IL_0000…002A` 对缩放输入零值、Picker 打开或菜单打开分别早退。通过三个门后才计算 z、调用 `ClampZ` 并设 Transform.position (`IL_002C…0089`)，随后调用 `SetPixelation` (`IL_008E…008F`)。故普通 `Update` 每次**调用 ZoomCamera**，但只有非零且未被 UI 挡住的输入才走 `SetPixelation`；即使 Clamp 后 z 恰与旧值相同，此分支仍可调用它。`Start` 另有一次初始调用，见 [22](22-pixel-grid-camera-motion-and-silhouette-stability.md)。`SetPixelation 0x060000C7 / IL_0079…0085` 写 feature 的 `_maxResHeight`；写设置不等于每次重分配纹理，[10](10-low-resolution-mips-and-attachments.md)已列出附件复用门。

## 配色应用由入口与协程驱动

REA 对 `ColorManager` 的本类型 9 个 MethodDef 完整枚举中没有 `Update`。本类 `Start 0x060000D3` 直接应用 Sun；`BlendToSun/Rain/Night 0x060000D4…D6` 进入 `BlendToPalette 0x060000D7`，后者停止旧协程并启动新过渡；`ApplySavePalette 0x060000D2` 还可走零时长切换，详见 [19](19-palette-propagation-and-shared-state.md)。因此不能把 [19] 算出的条件路径材质写入量乘上每个空闲帧，也不能由无本类 `Update` 推断别的调用者或渲染通道不写颜色。

`<BlendCoroutine>d__17.MoveNext 0x0600034C` 初始化 `timer=0` (`IL_0017…0029`)；当 `timer < duration` 时，先将 `blendFactor=timer/duration`，再加 `Time.deltaTime`，调用 `ApplyBlend`，存 null current 并 `ret true` 交回一次 yield (`IL_002B…0077`，`IL_0080…008B` 回跳)。循环条件不成立时，把 factor 设为 `1`，**再调用一次** `ApplyBlend`，然后 `ret false` (`IL_008D…00B1`)。因此过渡中的多次颜色写入和完成时一次末次写入可由这段 CIL 支持；协程结束后本方法不会自行持续重跑。`duration=0` 不进入除法循环，仍有末次应用。每次 `ApplyBlend` 可触达共享材质、环境、天空、后处理、粒子等，实际分类曲线和监听边界见 [19](19-palette-propagation-and-shared-state.md)、[20](20-blend-curves-and-particle-listener-lifecycle.md)。本篇没有计量单次应用的 CPU/GPU/GC 成本。

**构造演算，非游戏帧观测。** 假设一次过渡的 `duration=1.0` 秒，每次协程恢复时 `deltaTime=0.25` 秒，且调度恰好持续：timer 依次以 `0、0.25、0.50、0.75` 进入循环，四次 `ApplyBlend` 后各 yield；恢复到 `timer=1.0` 时条件 `1.0<1.0` 为假，再以 factor `1` 应用一次并结束，共五次。与此同时若某帧相机没有输入，正常 `Update` 仍会进入 `Move` 的 Raycast／位置调用，却不会经零缩放的 `ZoomCamera` 改 `_maxResHeight`。实际协程恢复间隔、浮点累积、关卡配置和帧时均未知；此例只展示分支含义。

低分辨率 pass 是按相机渲染准入执行的画面工作，设置尺寸变化与实际重分配另有门；平面反射是每件反射组件针对合格源相机的回调，并复用其临时纹理，见 [25](25-reflection-texture-lifecycle-and-binding.md)。颜色过渡按协程恢复，移动逻辑按正常相机 Update；这些频率不同，不能概括为“所有效果每帧恒重建”，也不能静态断言全游戏零重复或哪条路径是性能瓶颈。

**Answered（静态）**：正常相机 Update 的调用顺序与传送一帧跳过门、零移动时 Move 的 Raycast/位置调用、缩放/菜单/Picker 的像素设置门、ColorManager 无本类 Update、协程逐次及末次应用。**Partial / Unknown**：实际 scene 与组件生命周期、别的颜色调用者、Unity API 对零移动的内部代价、协程实际恢复次数、渲染／反射准入频率和真实性能。**Not Run**：游戏/Unity 启动或附加、私有存档、目标方法执行、帧时/GPU/GC 捕获、软件安装。

**Focused 静态核对：Passed。** [独立回执](../../../../.cache/procedural-modeling/steady-performance-followup/summerhouse/focused-validation-26.json)对比普通离线 CIL 与两条**正确命中**的 REA 记录：10 个选定方法合计 208 个 REA anchor 一致，且检查完整方法数、ColorManager 无 `Update`、关键调用／分支和错误类型请求的零命中。结果 `Passed=25, Failed=0`；验证只证明文件内 CIL 和证据对应，不证明运行频率或耗时。
