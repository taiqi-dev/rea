# SUMMERHOUSE：晴雨夜调色板怎样传播到共享状态

后续[20](20-blend-curves-and-particle-listener-lifecycle.md)补上真实分类曲线和14件scene监听实例，并修正退订概括：OnDisable调用退订入口，但该实现非空列表直接返回，不能等同实际移除。动态集合与实际通知仍未运行验证。

本篇接续[03：换色与保存](03-save-palette-and-visuals.md)、[05：真实材质绑定](05-materials-pixelization-and-camera.md)。**Lake场景的三套调色板使用同序的84个不同材质引用，但天气／时间变化同时修改环境光、灯、天空、雾材质、后处理和粒子共享变量。**它不是每个建筑块各存一份颜色，也没有在这条换色链里重建块网格。普通过渡入口会跳过地形detail/layer直接应用，不能把资产里保存的所有参数都算作每次切换会生效。

## 真实配置：三套完整资产与场景连接

输入固定为 `C:\Software\Steam\steamapps\common\SUMMERHOUSE\SUMMERHOUSE_Data` 内的 `Assembly-CSharp.dll`、`globalgamemanagers`、`globalgamemanagers.assets`、`sharedassets0.assets`、`sharedassets1.assets` 和 `level1`；沿用[00](00-evidence-and-scope.md)身份，未重算摘要。DLL MVID为 `84569538-a19f-4c17-8ccf-f40b95e99253`。使用既有离线[CIL读取器](tools/ManagedCilProbe/Program.cs)和本轮[参数读取器](tools/palette_asset_probe.py)，不加载执行目标程序集。

读取器按精确 `2023.2.22f1` Release树完整消费原生MonoScript、Material和BuildSettings；资源format22、无type tree。自定义布局由本作DLL字段类型及序列化资格约束：ColorPalette有29个序列化字段，六类内嵌记录的成员顺序分别从metadata核对；ColorManager有7个序列化字段。三个调色板及选定manager均**完整消费到对象末尾**，不以任意位置的引用命中代替解析。

| 文件／对象                 | 身份与读取范围                                  | 与场景的连接                                                       |
| -------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| sharedassets1.assets / 107 | ColorPalette Lake Night 01，偏移4276008，6200 B | level1 manager的Night引用                                          |
| 同文件 / 108               | ColorPalette Lake Rain 01，偏移4282208，6200 B  | manager的Rain引用                                                  |
| 同文件 / 109               | ColorPalette Lake Sun 01，偏移4288408，6196 B   | manager的Sun引用                                                   |
| level1 / 511               | ColorManager，偏移2360272，92 B；m_Enabled=1    | 三个PPtr均经外部表接到上述资产；activePalette=0，blendDuration=1.5 |

BuildSettings的scene数组索引1为 `Assets/Scenes/Environment Lake/Environment Lake.unity`，与level1坐标对应。manager的enabled字节和资源存在不等于当前正在运行该场景。五份发行level的脚本引用检查另见raw `manager-locations.json`，其余场景的配色对象未在本篇展开。

每套资产都有84个主材质颜色记录、4个附加材质记录、7个地形detail记录、3个地形layer tint记录及7个共享变量记录。主材质引用、MaterialName和共享变量引用均逐项核对三套顺序一致。主材质PPtr的file3指向 `sharedassets0.assets`；雾等附加材质在本地文件。原生Material读取完整，但raw仅保存其名称／shader投影，不导出贴图或网格。

## 从入口到写端

`ColorManager.Start 0x060000D3 / IL_0000…0028` 用Sun各建一份source和blend副本，然后调用Sun的 `ApplyAllColors(false)`。`BlendToSun/Rain/Night 0x060000D4…D6` 使用对应目标和manager的duration；`BlendToPalette 0x060000D7` 从当前blend复制出新source，停止旧协程，再启动新过渡。因此中途换目标的可见代码从当前混合参数接续，而非只在三套资产中跳选起点。`activePalette`在入口立即写入，不能作过渡已经结束的凭据。

协程 `ColorManager+<BlendCoroutine>d__17.MoveNext 0x0600034C` 以 `timer/duration` 设置blendFactor，用deltaTime推进timer，每次调用 `ApplyBlend` 后yield；循环结束将factor设1并再调用一次。`ApplySavePalette 0x060000D2` 的切换分支传duration=0；协程先做循环条件，故这条分支跳过循环中的除法，直接走factor=1的末次应用。它仍经过分类曲线处理，不能把factor=1无条件替换为每一分类权重都恰为1。

`ApplyBlend 0x060000D9` 先调用 `ColorPalette.Lerp 0x060000EE`，再对blend副本调用 `ApplyAllColors(true)`。Lerp对环境光、灯、天空、雾／附加材质、后处理、共享变量、普通材质、例外材质和音量分别取曲线权重；普通材质按同索引MaterialName相等才加入输出，例外材质走另一条曲线。当前三套资源84项名字和引用对齐，满足这一静态前提。没有把实际AnimationCurve数据解出，因此不承诺“时间走到一半就是颜色中点”。

| 消费方法／token                                | 实际写入                                                                                                                                      | 传播边界                                                                                  |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| ApplyMaterialColors / DD                       | 每项Material.SetColor：`_BaseColor`、`_EmissionColor`                                                                                         | 直接写共享Material引用；没有在这里逐Renderer实例化Material。                              |
| ApplyLightingSettings / E1                     | RenderSettings的ambientSky/Ground/EquatorColor                                                                                                | 全局环境参数；不等于最终像素或当前ambientMode必消费三色。                                 |
| ApplySkyboxSettings / E3                       | 同一Skybox Material的SunSize、AtmosphereThickness、SkyTint、GroundColor、Exposure，再设RenderSettings.skybox并调用DynamicGI.UpdateEnvironment | 非空skybox引用门；实际GI更新成本、完成时刻未知。                                          |
| ApplyDirectionalLightSettings / E8→035B        | 查得Light后写intensity、color                                                                                                                 | 有Unity对象有效性门；查询的实际运行对象尚未观察。                                         |
| ApplyAdditionalMaterials / DF→0354…0356        | 4项附加Material的BaseColor／EmissionColor                                                                                                     | 两项雾材质和两项粒子材质；没有在本方法写RenderSettings.fogColor。                         |
| Lerp / EE，ApplyPostFX / E9                    | Lerp给两个Main PostFX Volume设A/B profile及互补weight；直接应用给B设所选profile                                                               | 过渡路径单独处理，ApplyAllColors(true)跳过E9；Volume是否激活、profile参数与最终画面另证。 |
| ApplyParticles / EA→035D                       | 每个共享变量先set_Value，再set_ColorValue                                                                                                     | setter通知已注册且非空的listener；不是只改变调色板副本。                                  |
| ApplyTerrainDetailColors / E5、LayerTints / E7 | detail的healthy/dryColor，TerrainLayer.diffuseRemapMax，之后写回数组                                                                          | **false入口才调用**，true入口跳过；本篇所查普通过渡末次也保持true。                       |

`SharedVariable.set_Value 0x06000266` 和 `set_ColorValue 0x06000268` 均遍历listeners调用SetValue；`SharedVariableListener.SetValue 0x06000270` 按变量type的0/1分支分别写ParticleSystem emission.rateOverTime或main.startColor。OnEnable先订阅再应用，OnDisable调用退订入口；[20](20-blend-curves-and-particle-listener-lifecycle.md)复核出其非空列表直接返回，因此不能概括为已经移除。这里接通了共享变量到粒子参数的消费，运行订阅列表与实际发射数仍未恢复；选定scene实例以后续20为准。

主材质在[05的普通窗](05-materials-pixelization-and-camera.md)中已有具体消费者：`Window 07` 的Model01 Renderer4542含Material57 `Glass 01 b`，人物窗Renderer4986也复用它。因此下面夜色玻璃参数写入会沿共享引用影响这些已实例化且仍使用该材质的对象；每扇窗无需各自存储一份天气色。实际场景实例／覆盖、相机可见性仍是条件。

## 真实端点参数与构造演算

以下为资产float32参数，显示小数作四舍五入；不是屏幕采色值，HDR分量不裁成0…1。三套Skybox均指向共享assets0/102；地形均指向sharedassets1/122。

| 参数                              | Sun                          | Rain                         | Night                        |
| --------------------------------- | ---------------------------- | ---------------------------- | ---------------------------- |
| Glass 01 b Base RGB               | (0.325082,0.546839,0.783311) | (0.409710,0.634100,0.933962) | (0,0,0)                      |
| 同材质Emission RGB                | (0,0,0)                      | (0,0,0)                      | (0.339623,0.112209,0.008010) |
| 灯intensity                       | 1.30                         | 0.85                         | 0.70                         |
| ambientSky RGB                    | (1.152636,1.140554,1.320278) | (0.341002,0.482625,0.745283) | (0.072891,0.493740,0.735849) |
| Skybox Exposure                   | 4.32                         | 3.14                         | 0.30                         |
| Fog Material的Base alpha          | 0                            | 0.8                          | 0.698039                     |
| Fog Material Fadeable的Base alpha | 0                            | 0.360784                     | 0.086275                     |

构造演算：以真实Sun和Night为端点，**额外假设**玻璃所属分类的有效曲线权重为0.5，且84项匹配、无运行覆盖，则Material57的混合Base RGB约为 `(0.162541,0.273419,0.391655)`，Emission约为 `(0.169811,0.056105,0.004005)`。Lerp把它放入新颜色记录，ApplyMaterialColors写共享Material，再由后续绘制读取。若灯自己的分类权重也为0.5，灯强度约1.0；这与材质分类权重相等只是本例假设。它没有证明过渡第0.75秒的实际值，更没有把发光参数等同于夜窗像素亮度。

## 静态成本与未应用的参数

当前84项对齐且正常走完整方法时，一次ApplyBlend包含两次主材质应用：Lerp的 `IL_0578` 调ApplyMaterialColors，随后ApplyAllColors(true)的 `IL_0001` 又调一次。由本体循环可计 `84×2属性×2次=336` 次Material.SetColor调用；4项非空附加材质再给8次。这个 **344次调用** 不含天空的5个属性写入、灯、环境、粒子、Volume或实际Unity内部成本；它也不等于344个draw call。

同一Lerp在两端数量相等的分支新建两个List，以及7个SharedVariableSettings和84个MaterialColorPair记录；这表明有托管分配来源，未测GC字节或停顿。7个共享变量在Lerp中ApplyVariables一次，随后ApplyAllColors(true)又应用一次；每次ApplyVariables写float及color两个setter。因此该条件路径有28次setter的listener列表遍历。实际监听数量、某分类是否启用、目标调用成本和每秒次数均未测，不能用这些静态次数报告FPS或性能问题。

地形的7/3项虽然存入三套调色板，但本篇普通Blend链的true门不直接写这些项；未发现协程完成后补调false入口。Start的Sun直接应用会写它们，其它调用者仍须按入口核对。声音过渡和后处理在Lerp另有处理，分类曲线、音量控制消费者与profile具体参数未完整展开。资产存有字段、方法会写字段、某条切换入口实际调用该方法是三个不同证据层。

## 复算、验证与剩余问题

新普通raw在 `.cache/procedural-modeling/static-state-followup/summerhouse/`：`color-palette.json`、六个内嵌类型的metadata/CIL、`color-manager.json`、`blend-coroutine.json`、`shared-variable.json`、`shared-variable-listener.json`、`palette-callers.json`、`palette-assets-v3.json`。`palette-callers.json`覆盖本DLL173个类型、1006/1006方法的离线操作数搜索，不覆盖其它程序集、反射或UnityEvent序列化调用。v3为正式读取器当前投影；早期v1/v2保留为开发记录，不替代它。

```powershell
python -X utf8 docs/studies/procedural-modeling/summerhouse/tools/palette_asset_probe.py --game-data 'C:/Software/Steam/steamapps/common/SUMMERHOUSE/SUMMERHOUSE_Data' --schema .cache/procedural-modeling/static-resource-followup/reference/2023.2.22f1-InfoJson.json --metadata-dir .cache/procedural-modeling/static-state-followup/summerhouse --output .cache/procedural-modeling/static-state-followup/summerhouse/palette-assets-recheck.json
```

Answered：三套真实资产及Lake manager连接、84项共享材质对齐、关键端点值、静态应用／混合／中途换目标路径、环境与粒子写端、普通过渡的地形跳过门。Partial：分类曲线数据、全部listener对象、实际Light选择、Volume profile参数和场景运行覆盖。游戏、目标函数、GPU、私人存档、画面／声音、帧时／GC测量均 **Not Run**；REA既有native Ghidra超时未变、未重试，普通文件不冒称REA Evidence。

独立设计可把天气状态集中为少量参数组，明确共享材质、全局环境、粒子与地形各自的应用门；过渡用当前混合状态作下一段起点，并将“选中目标”与“过渡完成”分开。静态重复写入和分配可作为自研预算的检查项，不能直接推断原作真实瓶颈。
