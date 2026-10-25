# Tiny Glade：自动焦点参数的实际来源

2026-10-24，America/Los_Angeles。续 [161](161-tiny-glade-dof-focus-and-near-far-blur.md)，补 CPU 参数到 shader 的对应，不读取用户配置或启动游戏。树木条件见 [164](164-tiny-glade-tree-settings-and-cone-producers.md)，深度记录见 [165](165-tiny-glade-scene-depth-to-focus-and-coc.md)。

## 本轮回答了什么

自动焦点的采样位置并非总是屏幕中央，也不是一律跟着鼠标：所选分支可以从当前相机的配置点计算，也可以从 `CursorPositionSS` 和 `WindowSize` 计算。锁定参数另从 `PhotomodeState` 取得；光圈与 tilt-shift 来自当前相机镜头。**CPU 的焦点选择参数、GPU 的 focus0/1 距离结果是不同数据。**

本轮继续只读 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）及同目录匹配 PDB，GUID/age 沿 [153](153-tiny-glade-ground-startup-grid-and-background-seams.md)。使用现有 PDB、dumpbin 和 SPIR-V reader；上一轮 REA native 超时没有相关前提变化，未重复长分析，不把普通文件证据称为 REA Evidence。新原始记录在 ignored `.cache/procedural-modeling/tiny-dof-followup/`。

## 资源身份：从“附近有这个名字”到同一类型键

`calculate_dof_autofocus`（preferred VA `0x140B38410`）的五个资源查询，与 PDB 明确命名的 `App::insert_resource<T>` 各自读取同一份 16 B 类型标识字面量：

| 已确认资源                                      | typed insert 入口 | 自动焦点中读取类型字面量的位置 |
| ----------------------------------------------- | ----------------- | ------------------------------ |
| MainCamera                                      | 0x140287580       | 0x140B3861E                    |
| AppMode                                         | 0x141901290       | 0x140B38470                    |
| WindowSize                                      | 0x14028FC90       | 0x140B38555                    |
| CursorPositionSS                                | 0x141905BB0       | 0x140B388B9                    |
| PhotomodeState（startup::init_photomode_state） | 0x140297020       | 0x140B38749                    |

比较的是制品内原有 TypeId 字节，不是计算内容摘要。它使资源身份不再只依靠字段尺寸或调用附近的名字。

`MainCamera::mode`（`0x140A36620`）读取 `+0x4D0`；`lens`（`0x140A36600`）和 `focus`（`0x140A368D0`）分别按该值选择偏移，再加 `0x100` 返回子对象。自动焦点使用的两张选择表与这些 getter 的偏移逐项一致，本轮核了 tag 0..5 的六项，**没有把这些 tag 自行补成六个 UI 模式名称**。

## 绑定后的准确字段对应

`calc_autofocus::bind_entry_point`（`0x140BDCCC0`）将传入块写成 shader uniform。资源参数与普通数值在原块内会重排，不能按 CPU 写入先后猜 uniform 顺序。

| shader uniform     | CPU 来源/绑定                                | 已证边界                                                                   |
| ------------------ | -------------------------------------------- | -------------------------------------------------------------------------- |
| depth_tex_dims     | 从传入深度 TexView 的尺寸读取，写 uniform +0 | 与下面 WindowSize 不是同一来源                                             |
| point_uv           | 调用者块 +0x18 → uniform +8                  | 配置点或光标分支，见下文                                                   |
| use_dual_focus     | 调用者 +0x24 → uniform +0x10                 | 所选配置点分支为 0，光标分支为 1；全部有效选择枚举未命名                   |
| focus_lock_request | 调用者 +0x28 → uniform +0x14                 | 默认 raw 0xFFFFFFFF；所选拍照相关分支从 PhotomodeState +4 取得             |
| focus_is_locked    | 调用者 +0x2C → uniform +0x18                 | AppMode raw 16 且焦点选择 raw 0/1 时设置为 1；这不等于已观察 UI 锁定全过程 |
| focus_box_height   | 调用者 +0x30 → uniform +0x1C                 | 来自当前 focus 子对象 +0x18                                                |
| use_tilt_shift     | 调用者 +0x34 → uniform +0x20                 | 来自当前 lens 子对象 +0x28 的字节                                          |
| aperture_size      | 调用者 +0x20 → uniform +0x24                 | 来自当前 lens 子对象 +0x18 的 float                                        |

其中 CPU binder 对应读取在 `0x140BDD013–0x140BDD04F`，光圈另在 `0x140BDCD00–0x140BDCD03` 写到末项。shader 的实际成员装饰给出 +0/+8/+0x10…+0x24，避免把“光圈出现在 CPU 块较早位置”误当作 use_dual_focus。

这里的 MainCamera 镜头与 `ImageFormationConfig.camera_lens` 是不同容器；名字都含 lens，不能跨对象套用偏移。

## 采样位置的两条路径

`0x140B3881C–0x140B389AB` 按当前 focus 子对象首个 raw 选择值分派。对本轮选定的 raw 输入：0/1/4 使用 focus +0x10/+0x14，3 使用 +4/+8；2 进入光标分支。没有恢复完整选择枚举的合法域与 UI 名称，不将其称为全部模式清单。

配置点 p=(x,y)、窗口宽高比 a=W/H 的结果是：

```text
point_uv = (0.5 + 0.5*x/a, 0.5 - 0.5*y)
```

光标分支则为：

```text
point_uv = (CursorPositionSS + (0.5,0.5)) / WindowSize
```

两者都不是“直接把世界坐标喂给景深”。当前代码使用 WindowSize 做归一化，shader 再用自己的 depth_tex_dims 取样；最终 viewport、DPI 和所有相机布局的转换规则尚未完全恢复。

**构造例，非运行。** W/H=1920/1080、配置点 (.8,.4) 得 UV=(.725,.3)；窗口 800×600、光标 (399.5,299.5) 得 (.5,.5)。光标值中的半像素是构造输入，不声称操作系统必定返回这种坐标。

AppMode raw 16 与焦点选择 raw 0/1 的组合会额外查询 PhotomodeState，读取 +4，转交锁定请求并设置对应输入标记；其他选定路径保留默认 raw 请求和未锁输入。GPU `DofAutofocus.is_locked`、锁点插值与读回响应是另一层状态，不能仅凭 CPU 标记断言锁定已经成功。

## 自研取舍与未决项

适合综合 demo 的行为规格：焦点策略明确区分画面点、鼠标点和锁定世界点；按当前视图统一生成参数，正确处理窗口与实际渲染尺寸的差别。不要让每个物体自行争夺景深焦点，也不要把 AppMode、MainCamera.mode、shader camera_idx 三种索引混成一个 enum。

还未回答配置点/选择值的全部 UI 写端、默认设置、所有模式切换与锁定恢复，以及每条插值曲线。本轮 `SymGetTypeFromNameW` 对五个候选名均失败并记录 error 1；没有据此声称 PDB 无类型，而改用精确 typed insert、getter 和 binder 指令核对。宽查询触顶与长符号 NUL 后的内容不用于完整性或类型结论。

[dof_followup_probe.py](tiny-glade/tools/dof_followup_probe.py) 已复核五组类型标识、相机选择表、相关字面量与深度绑定；例子只做独立演算。游戏、GPU、Unity、配置实际值和手感验证均 **Not Run**。
