# SUMMERHOUSE：遮罩相机的排序与渲染入口条件

[14](14-vertex-color-mask-and-local-updates.md)已接通顶点alpha写端，本篇补遮罩纹理与主相机之间的调度条件。**同一URP相机列表若同时包含本场景两台相机且配置未变，Masking Camera的depth=-1排在Main Camera的depth=1之前。** 这是当前资源与托管调度代码的静态连接；原生侧是否把两台相机送进本次列表、实际GPU执行和重绘频率仍未观察。

## 相机、层级与追加配置

沿用[00](00-evidence-and-scope.md)、[11](11-mask-target-and-camera-overrides.md)的同版安装与程序集身份，不重新计算摘要。新增[相机顺序读取器](tools/camera_order_probe.py)从当前 `level0` 对象表读取两个Camera、GameObject和祖先Transform，并完整消费这些原生类型对象及关联MonoScript。两台相机的GameObject均为active，Camera本身enabled=1；祖先链为：

```text
VISUALS (GO915 / Transform2150, active=1)
  Camera Manager (GO526 / Transform2140, active=1)
    Main Camera (GO1055 / Transform2159, active=1)
      Masking Camera (GO1658 / Transform2180, active=1)
```

因此遮罩相机是主相机的实际Transform子对象，不是仅有名称关联；它的世界位置还会受父变换影响。[11](11-mask-target-and-camera-overrides.md)的投影参数读取相机当时的世界位置，父子关系只解释这个输入的上游，不证明各脚本Update/LateUpdate的真实先后或所有帧中的位置。

| 当前对象           | Camera字段                                                                        | 关联UniversalAdditionalCameraData的选定前缀                                             |
| ------------------ | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Main Camera2196    | 文件468720，184 B；depth=1；targetTexture=null；targetDisplay=0                   | pathID7384，文件1131824，180 B；enabled=1；cameraType=0；stackCount=0；rendererIndex=-1 |
| Masking Camera2197 | 文件468904，184 B；depth=-1；targetTexture=(2,765)，即MaskingMap；targetDisplay=1 | pathID8109，文件1284160，180 B；enabled=1；cameraType=0；stackCount=0；rendererIndex=1  |

AdditionalCameraData的 `m_Script=(1,1564)` 从同目录external表接到MonoScript，类/程序集名核对为 `UniversalAdditionalCameraData / Unity.RenderPipelines.Universal.Runtime`。它的自定义部分只按本作字段序列读取到对象+56，**尚余124 B未解析**，不称为完整自定义类型消费。所查连续字段是 `m_RenderShadows`、两个纹理选项、`m_CameraType`、空 `m_Cameras` 数量、`m_RendererIndex`；来源是同DLL的字段metadata，renderer偏移也与[05](05-materials-pixelization-and-camera.md)已有读取一致。本篇保留这段窄布局的适用边界。

同DLL的 `CameraRenderType` 常量把0/1分别声明为Base/Overlay；`get_renderType 0x06000723 / IL_0001` 直接读 `m_CameraType`。据当前前缀两者为Base且各自stack为空，不能因为存在父子Transform就将遮罩相机称为主相机的Overlay stack。

## 实际比较器先转整数，再相减

本作URP构造 `UniversalRenderPipeline..ctor 0x060007F4 / IL_0021..0032` 把 `<.ctor>b__37_0` 委托赋给 `cameraComparison`。该比较器 `0x06000834` 的全部有效步骤是读取两相机depth，各做一次 `conv.i4`，然后相减。`SortCameras 0x06000820` 只在列表长度大于1时调用同一比较器的 `List.Sort`。

对当前值的构造演算是 `int(-1)-int(1)=-2`，所以两台同时在列表中时遮罩在前，主相机在后。不能把该实现概括成任意浮点depth的严格大小排序；例如构造值0.2和0.8在这个转换下均为0，比较结果为0。本篇不推导并列项的稳定顺序、非有限值或溢出行为，当前两个序列化值没有这些情况。

主流程 `UniversalRenderPipeline.Render 0x060007F8` 在 `IL_0092` 调 `SortCameras`，随后取得相机列表迭代器；`IL_00A4..00AD` 对游戏相机调用 `RenderCameraStack`，其他相机走单相机内部入口。不是依据相机层级顺序依次渲染。[12](12-mask-camera-filter-and-shader-data.md)已经说明Masking Camera只选层8并用无像素化renderer；主相机排除层8并消费全局遮罩。这些条件合起来形成**有先后次序的生产/消费入口**，仍不代替具体图节点、设备同步或同帧可见像素证据。

`RenderCameraStack 0x06000800 / IL_0016..0028` 还会检查追加数据：如果renderType=1（Overlay），作为列表根进入时提前返回。当前选定前缀是0，不能用此Overlay门解释该静态配置下遮罩相机被跳过；其它门、renderer状态和原生列表选择仍未穷尽。

## 原生列表选择与普通渲染、请求路径的区别

CoreModule的 `RenderPipelineManager.DoRenderLoop_Internal 0x06002F86` 先准备pipeline，清空共享相机列表，经 `ScriptableRenderContext.GetCameras` 填入相机。`IL_0036..004C` 在请求参数为null时把该列表交给当前pipeline的 `InternalRender`；另一分支 `IL_0054..0066` 取列表第一台相机并调用 `InternalProcessRenderRequests`。正常返回后清空列表。**原生GetCameras如何决定本次成员没有在本篇恢复**，因此序列化enabled/active、targetTexture或targetDisplay不能单独证明相机已被送进列表。

游戏程序集范围173个TypeDef、1006个MethodDef全部解码后，直接 `Camera.set_depth` 命中0；直接 `Behaviour.set_enabled` 仅命中InputManager的虚拟输入设备和StartUpManager自身两个方法，没有以Camera为接收者的直接写入。这个范围不排除GameObject激活、父级状态、其它程序集、反射或原生侧变化，也不能证明depth在运行时永久不变。读取这些方法只为辨别接收者，未执行输入设备或界面操作。

`MaskingManager.Update` 每次只更新全局纹理引用与投影参数，没有调用Camera.Render；这和相机被调度、目标被重新写入是两个动作。当前普通托管列表遍历也没有在这两台相机前按“建筑是否dirty”做专属缓存门。本篇因此不宣称“只有编辑时才重绘”，也不由一次SetGlobalTexture推断“每显示帧必定完整重绘2048²”。

[11](11-mask-target-and-camera-overrides.md)的截图方法只明确对主相机调用Camera.Render，并临时改主相机目标；不能把上述普通列表条件自动推广为每次截图都先更新MaskingMap。手动Render与渲染请求最终采用哪个入口及相机集合，仍需继续静态接入或另行运行验证。

## 复算与状态

新原始输出位于 ignored `.cache/procedural-modeling/static-other-writers/summerhouse/`：`camera-order-and-hierarchy.json`、`additional-camera-type.json`、`camera-render-type-enum.json`、`camera-comparison-writer.json`、`depth-comparator.json`、`sort-cameras.json`、`render-camera-sort-callers.json`、`render-camera-stack.json`、`core-render-loop.json`、`behaviour-enable-writers.json` 和 `camera-depth-writers.json`。CIL工具只解析PE metadata与方法体，没有加载目标程序集执行。

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/camera_order_probe.py --scene "C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data/level0" --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --output .cache/procedural-modeling/static-other-writers/summerhouse/camera-order-recheck.json
```

读取器拒绝已有输出、错误版本、引用越界/非本目录、层级环或不支持的追加数据前缀。**Answered（静态）：** 两相机配置与active祖先、追加数据的选定前缀、比较器及列表内顺序、普通渲染与请求入口的分离。**Partial：** 追加数据其余124 B、GetCameras原生准入、动态变化、截图调度、实际重绘频率和设备执行。**Not Run：** 游戏、相机绘制、GPU、截图、像素和性能测量。
