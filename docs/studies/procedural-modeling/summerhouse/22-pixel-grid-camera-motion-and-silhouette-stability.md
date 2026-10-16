# SUMMERHOUSE：像素网格、相机移动与轮廓稳定的边界

后续[23：最终投影与像素对齐](23-final-projection-and-pixel-alignment.md)继续到URP矩阵初始化／提交和Shader622前向vertex消费，并核对fixed目标的viewport分支；最终native矩阵与GPU常量仍未观测，不把本篇局部无取整扩成全游戏否定。

接续[05](05-materials-pixelization-and-camera.md)、[07](07-pixel-blit-depth-and-local-render-route.md)和[10](10-low-resolution-mips-and-attachments.md)。**所选主镜头把指定层重绘到低分辨率颜色／深度，再用Point采样回贴；真实CameraController会按缩放曲线改变目标大小，但移动位置连续更新。**本轮找到的是控制像素尺度的链，没有证明世界轮廓锁在固定像素网格上，更没有运行观察到抖动或完全稳定。

## 身份与本轮读取

输入仍为 `C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data`。REA本轮静态读取主程序集CameraController与PixelateLayer，Evidence `ev_5f4266faed6f3cf41a49716a43f340f6000d0583c5961dcfcb1cc1b4afbc0e26`，metadata complete、两个精确类型均命中；MVID `84569538-a19f-4c17-8ccf-f40b95e99253`，186880 B，SHA-256 `f4e8bf23299a5e4a916d4bd955e108d2f3760117e5850adf10926ee6aa8379de`，与既有身份一致。摘要沿用此前对该目标调查的授权，不是新增权限请求。完整Evidence与普通CIL／资源输出分开放在ignored `.cache/procedural-modeling/static-art-followup/summerhouse/`。

[新只读探针](tools/camera_pixel_grid_probe.py)按当前DLL字段metadata和精确2023.2.22f1 Release树扫描level0…4；只找到一件CameraController。完整解析它、关联feature、原生Camera／Transform／GameObject及相机祖先链；其他MonoBehaviour只解析script引用前缀。没有执行原生AnimationCurve.Evaluate、加载目标程序集或进入Unity。URP基类字段metadata来自本机644608 B的Runtime DLL，MVID `441516f4-c7ab-401e-840b-a71a7013b536`；CoreModule的Mathf CIL来自本机1717496 B、MVID `f07e5f68-ed2b-4769-8d43-49b644099efa`。

## 真实配置把缩放接到哪张像素网格

| 对象             | 当前资源位置／完整消费量                     | 关键值与连接                                                                                                                                  |
| ---------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| CameraController | level0/6732，文件1005848，260 B              | GO526 Camera Manager；moveSpeed=6、moveSmoothness≈0.2、zoomSpeed=1；minMaxZoom=(-5,-25)，minMaxPixelHeight=(150,300)，startPos=(47,1.5,-10)。 |
| PixelateLayer    | globalgamemanagers.assets/2360，934000，76 B | Controller的外部引用实际指向它；m_Active=1，mask471、pixelScale1、maxResHeight初值251，最终Shader65。包括URP基类m_Active在内全部字段消费。    |
| Main Camera      | level0/2196，468720，184 B                   | perspective（orthographic=0），FOV40，viewport全屏、targetTexture空、dynamicResolution=0。                                                    |
| 相机Transform    | level0/2159，465472，80 B                    | 子相机localPosition=0、rotation单位、scale1；父2140属于Camera Manager，再上层VISUALS也是单位旋转／scale。                                     |

三层相机祖先的组件只有Transform、Camera、UniversalAdditionalCameraData、AudioListener和CameraController；没有在这里找到PixelPerfectCamera或另一个像素对齐组件。这里是当前scene的静态组件范围，不排除运行添加或URP/native改矩阵。Camera Manager的序列化位置 `(69,2.7,-17.87)` 也不能充当Start后位置：`Start 060000C1 / IL_0011…0043` 明确写入startPos并调用SetPixelation。

`SetPixelation 060000C7`先分别取zoom两端的min/max，随后从**当前Transform世界z**计算：

```text
u = InverseLerp(-25, -5, z)
w = Evaluate(pixelationCurve, u)
Hmax = int_truncate(Lerp(300, 150, w))
feature._settings._maxResHeight = Hmax
```

`IL_0038…0077`取minMaxPixelHeight.y再x，不是150→300；`conv.i4`是截断，不是RoundToInt。当前CoreModule `Mathf.Lerp 06001BC5`先Clamp01(w)，`InverseLerp 06001BD5`也夹住归一化结果。这与[Unity 2023.2 Lerp说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/Mathf.Lerp.html)一致。因此曲线值超过1不会把Hmax推到150以下；对有效有限输入，这一步限制在150…300。

## 四个真实曲线节点与两次量化

pixelationCurve有四帧，均weightedMode=0。以下显示舍入值，完整float32与切线保存在raw；第三帧outSlope≈4.55145、末帧inSlope≈7.16227，不能当作一条线性曲线。pre/postInfinity均2，本轮不为其native枚举或末帧之后的Evaluate行为补名。

|       节点u | 保存的value | 对应说明用z=-25+20u | 按该节点value计算的Hmax | 假设输入1920×1080时的目标 |
| ----------: | ----------: | ------------------: | ----------------------: | ------------------------- |
|           0 |           0 |                 -25 |                     300 | 534×300                   |
| 0.258030236 | 0.106108591 |         -19.8393953 |                     284 | 504×284                   |
| 0.763207376 | 0.330101073 |          -9.7358525 |                     250 | 444×250                   |
| 0.857727051 | 1.007076263 |          -7.8454590 |         150，经Lerp夹值 | 266×150                   |

这是**以已存节点值代入的构造演算**，没有调用Evaluate；z经float32归一化未必逐位等于保存的节点横坐标，不把表当作具体位置实测结果。区间内所有值、曲线外wrap与实际逐帧zoom仍未运行。

`PixelateLayer.SetupRenderPasses 0600032F / IL_001D…007B`在Hmax整数之后再计算：

```text
s = max(pixelScale, inputHeight / Hmax)
Wlow = 2 * RoundToInt(0.5 * inputWidth / s)
Hlow = 2 * RoundToInt(0.5 * inputHeight / s)
```

[RoundToInt文档](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/Mathf.RoundToInt.html)明确中点取偶数，故Hmax=251时Hlow可为252，不能把“最大高度”当作严格不超过的最终附件高度。宽高还各自取偶数，纵横比只近似保持：444×250在1920×1080屏幕上每格约4.324×4.32屏幕像素，非整数倍。目标尺寸相同的某些zoom变化不会重新改变网格尺寸，但不代表世界投影位置不变；相邻Hmax也可能仅改变宽度。`ReAllocateIfNeeded`另有尺寸／格式等比较，设置方法被调用不等于每次分配纹理，见[10](10-low-resolution-mips-and-attachments.md)。

主程序集173个类型、1006/1006方法的`_maxResHeight`引用扫描只命中SetPixelation、Settings构造器、SetupRenderPasses。ZoomCamera `060000C4`只有非零缩放输入、picker／menu未打开时更新z、ClampZ，再调用SetPixelation；Start也调用。TeleportToPosition `060000CE`只写position和hasTeleportedThisFrame，在该方法没有同步调用SetPixelation。因此不能用Start或任意位移的存在推断像素目标必被同期刷新；其他调用者／后续缩放仍可触发。

## 为什么大像素不等于位置锁定

`ProcessInput 060000C8`对输入做SmoothDamp；`Move 060000C9 / IL_0077…0099`按currentMovement×moveSpeed×deltaTime连续Translate，随后限制位置边界。`DragCamera 060000CA`按屏幕位移、相机距离、FOV和屏幕宽高算世界位移并写position。`ApplyPositionBoundaries 060000C6`只Clamp，不Round。CameraShake协程 `MoveNext 06000346`取PerlinNoise偏移写子相机localPosition，末尾恢复原值，没有像素取整。是否真的触发shake另有调用条件，不由协程存在推出。

全主程序集Mathf.Round直接引用只在六个方法中：BuildingBlock.CalculateSoundIntensity、GridManager.RoundZDepth／SnapPositionToGrid、UtilityBasic.V3toV2Int／Round、PixelateLayer.SetupRenderPasses。没有从这些调用接到CameraController的position量化；整数建筑格点和相机像素对齐不是同一约束。对Camera setter的扫描则仅命中MaskingManager背景色和ScreenshotTaker目标纹理替换，没有主程序集直接projectionMatrix／FOV写端。这些阴性结论不覆盖其他程序集、native、字符串调用或运行添加组件。

最终采样复用[07](07-pixel-blit-depth-and-local-render-route.md)至[10](10-low-resolution-mips-and-attachments.md)：Shader65全屏三角形产生UV，Point／Clamp采低分辨率颜色和深度，输出SV_Target与SV_Depth；片元没有UV取整、轮廓检测或跨帧重投影。颜色／深度附件mip0，普通相机路径不开mip链；[16](16-additional-camera-layout-and-effect-gates.md)的主相机AA初值None。Point采样保留阶梯边，但非整数放大可能使屏幕上不同格覆盖不同数量像素；静态配置不能保证相机移动时每条边都固定不跳。

**独立投影例，非原作画面。** 假设当前是普通透视矩阵、FOV40、平面相机距离d=10、Hlow=250，纵向一个低分辨率像素约对应 `2d*tan(20°)/250≈0.02912` 世界单位。连续移动0.00728约为四分之一格；到d=20的同向平面，一个像素的世界跨度约加倍。同一世界取整步长不能同时对齐两个深度平面。[Camera.fieldOfView说明](https://docs.unity3d.com/2023.2/Documentation/ScriptReference/Camera-fieldOfView.html)支持其纵向角定义，也明确自定义投影矩阵可覆盖它；本例因此保留普通矩阵前提。是否在真实场景形成可见跳边要由运行证据回答。

## 更新、成本与已答边界

SetPixelation改变共享feature的尺寸参数；单块换色或组合修改改变对象Renderer／材质，另见[06](06-local-updates-and-render-costs.md)。所选像素化pass按当前cullResults和层筛选DrawRenderers，声明清理／复制后重绘该层并统一回贴，没有在这些方法中消费单块dirty屏幕矩形或复用上帧轮廓。它降低部分像素分辨率，也增加重绘、颜色／深度目标和合成步骤；没有帧时、显存峰值或实际draw call数据。

**Answered（静态）**：真实Controller→曲线→feature引用、完整配置／相机祖先、整数截断与偶数尺寸两级量化、缩放调用条件、连续位移与shake写端、局部对象修改到整层重绘的边界。**Partial／Unknown**：native曲线区间／wrap、URP/native最终矩阵和视口覆盖、运行添加组件、屏幕格宽不均是否可见、实际轮廓稳定与成本。并未证明游戏一定抖动，也没有找到足以保证完全稳定的像素锁。

复算：

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/camera_pixel_grid_probe.py --game-data 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --metadata-dir .cache/procedural-modeling/static-art-followup/summerhouse --output .cache/procedural-modeling/static-art-followup/summerhouse/camera-grid-config-recheck.json
```

检查范围为当前资源完整消费／复读、MVID与字段资格、CIL写端／分支、节点代入和float32尺寸算例、输出覆盖／错误profile拒绝、文档链接与语法。正式Evidence与普通raw均保留原范围；游戏／Unity启动、附加、目标函数或GPU执行、截图、私人存档和运行性能全部 **Not Run**。
