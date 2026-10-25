# Tiny Glade：树木渐隐设置、模式门和圆锥参数生产者

2026-10-24，America/Los_Angeles。续 [162](162-tiny-glade-tree-see-through-and-dof-composition.md)，身份与静态方法沿 [163](163-tiny-glade-autofocus-parameter-producers.md)。本轮接回设置的正式字段和圆锥参数来源；原来的手放树动画、树冠/树干片元条件继续有效。

## tree_see_thru 的真实归属

`ImageFormationConfig` serializer（preferred VA `0x14052CD40`）序列化三个入口：grading（对象 +0）、camera_lens（+0x30）、artistic（+0x3C）。最后一项的实际泛型 callee 类型是 `ArtisticConfig`。后者 serializer（`0x14052CB00`）依次使用 `lighting_only` 和 **`tree_see_thru`**；在两项之间增加源指针 1，因此后者是 ArtisticConfig +1，即 ImageFormationConfig **+0x3D**。

这把 [162](162-tiny-glade-tree-see-through-and-dof-composition.md) 的未知配置字节接回了有名称的设置，而不是从最终画面猜“透明选项”。同一安装包中的 `settings_see_thru.ron` 只是一个 UI FillColor 覆盖模板，不能凭 see_thru 名称把它误认为树木材质的开关实现。

`ImageFormationConfigs::current/current_mut`（`0x1409AA260`）按容器 +0xC0 的 kind 乘 64 选择一个配置；`switch_kind`（`0x1409AA270`）写该选择字节。选定构造函数 `0x1409A5FD0` 可见 +0x3D、+0x7D 的 true 写端和 active kind=1 写端。它们是构造与配置选择证据，不是玩家当前值，也不是所有配置/恢复路径永远为真的证明。GUI 复选框、读回配置的全部写端仍未贯通。

## 设置如何成为 shader 覆盖位

`prepare_frame_constants`（`0x1409252D0`）在 `0x1409256C7–0x1409257B3` 从当前 ImageFormationConfigs 选择的 64 B 配置读取 +0x3C/+0x3D。资源归属由 wrapper 的首个 tuple 中 `Res<ImageFormationConfigs>` 与函数的实际解包顺序核对；没有把 stack local 重用后的同一偏移当成永久同一变量。

`0x140925DE0–0x140925E13` 先备选 OR `0x2`，再按 AppMode raw 16、tree_see_thru、MainCamera.mode raw 3 选择；`0x1409262B5` 最后写入 FrameConstants +0xCC 的 render_overrides。正常 bool 与所选调试值下，位 `0x2` 的选定规则是：

| AppMode   | tree_see_thru | MainCamera.mode | 所选位 0x2 |
| --------- | ------------- | --------------- | ---------- |
| 非 raw 16 | 任意          | 任意            | 置位       |
| raw 16    | false         | 任意            | 不置位     |
| raw 16    | true          | raw 3           | 不置位     |
| raw 16    | true          | 非 raw 3        | 置位       |

raw 16 还在自动焦点中连接 PhotomodeState，见 163；本篇不由这一关联补齐全部 AppMode/UI 名称。**这个位的设置不是“当前像素景深很强就改为透明”。** 它也不是最终显示许可：树冠片元仍检查 is_firstperson_mode、动画值、距离与圆锥，树干有自己的附加条件。

因此不能直接把 tree_see_thru 当成所有模式共同生效的全局总开关；所选代码对不同模式有不同门控。

## 最大距离：已接回平滑状态

frame wrapper 的第二 tuple 末项 `Res<TreeCanopyMaxCullDistance>`，与 `0x140925436–0x14092543D` 的解包及后续读取一致：第二 tuple +0xC0 取资源数据，`0x140925BCA–0x140925BD1` 读其 +4。这个字段在 [162](162-tiny-glade-tree-see-through-and-dof-composition.md) 的手放树动画入口由全局状态的 smoothstep 结果写入。

```text
max_cone_cull_distance = 30 * TreeCanopyMaxCullDistance[+4]
```

乘法在 `0x140925D4C`，经临时槽保存后由 `0x1409263DB` 写 FrameConstants +0x13C。它不是每棵树各自固定“30 米必透明”；实例动画、相机投影尺度和每片元条件还会限制结果，数值单位也不擅自命名成物理米。

**构造例。** 若原全局进度 t=.5，所选 smoothstep 结果为 .5，则此字段为 15；t=0/1 时为 0/30。这说明全局可见范围本身也能平滑改变，而不只是树材质 alpha 在变。没有运行确认实际时间长度或任何空间双阈值滞回。

## 圆锥角：镜头 FOV 而非固定角度

`0x140925BA0–0x140925BC2` 按 MainCamera.mode 的另一张表读取镜头字段。该表与 `MainCamera::lens` 的六项偏移一致；所读的是 lens +4，而 `target_vertical_fov_degrees` 读取 +8。`CameraDofLens::immediately_set_vertical_fov_degrees`（`0x141A2E5B0`）同时写 +4/+8，配合后续角度换算确认它们属于 FOV 状态。

`0x1409260E5–0x1409260FF`、`0x1409263A8–0x1409263CA` 形成：

```text
cone_angle_mult = 0.8 * max(0.07, radians(lens_FOV_degrees)/2)
```

结果写 FrameConstants +0x138。**构造例。** FOV=60° 时约 .418879；FOV=4° 时受 .07 下限影响，得到 .056。实际树冠片元还把该值与距离项、实例 see-through 动画和噪声阈值组合，它不是最终所有树通用的单一可见圆锥角。

## 对综合 demo 的可借鉴规则

设置、全局过渡、实例动画、片元切口分开管理：模式决定是否允许，平滑状态控制影响距离，镜头 FOV 调整覆盖角度，再由当前树的资格和动画参与局部覆盖。景深仍是另一条深度/焦点处理链，无须为了借鉴风格增加“树与建筑的效果优先级仲裁器”。

我方若要一个用户可理解的总开关，应明确它在普通编辑、拍照、第一人称及预览视图的作用，而不是照抄 raw 分支后留下某些模式不生效。继续复用现有相机/表现所有者；不为展示状态增加第二套世界、保存或时钟。

仍未知：所有 GUI/加载写端、profile kind 的完整产品标签、森林树与手放树的全部更新资格、空间滞回和真实延迟。[dof_followup_probe.py](tiny-glade/tools/dof_followup_probe.py) 已读取并核对字段名、分支锚点、镜头偏移及 .8/.07/30 等实际常量。游戏、GPU、Unity、画面和性能验证均 **Not Run**。
