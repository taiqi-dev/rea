# Tiny Glade：受光公式、柔和阴影与历史稳定

2026-10-22，Pacific Time。续接 [137：渲染框架](137-tiny-glade-renderer-language-lighting-and-demo-route.md) 和 [119：级联预算](119-tiny-glade-shadow-cascades-and-work-budgets.md)。本篇解释选定 shader 的实际计算；Unity 的独立实现建议见 [143](143-unity-urp-cozy-style-independent-rendering-plan.md)。没有运行游戏或检查用户工程。

**选定实体光照包含粗糙漫反射、微表面高光、遮挡和间接照明；柔和阴影包含遮挡者搜索、可变范围比较采样及历史限幅。** 因而不能把画面概括成一条卡通明暗分界，或仅靠提高阴影分辨率。

## 身份和定位

沿用本研究已匹配的 `C:/Software/Steam/steamapps/common/Tiny Glade/tiny-glade.exe`（65,612,184 B）与同目录 PDB，未新算摘要。shader 根为 `compiled-shaders/country-core/compiled/`。本轮使用现有 DbgHelp、VS dumpbin 和 [SPIR-V 结构读取器](tools/spirv_probe.py)；此前 REA native 全程序分析超时的前提没有改变，没有重复相同长任务，也没有把普通文件证据写成 REA Evidence。

下文 `w` 是**模块内 word 偏移**：`deferred/solid_light_sun_sky.precomp` 片元模块字节起点 1243、20348 words；`apply_screen_shadows.precomp` compute 起点 112、5463 words。容器文件偏移为 `起点+4*w`，不要与旧报告的十六进制容器字节偏移混用。

## 实体受光不只是 Lambert

实体光照片元先从 G-buffer 恢复法线 `N`、RGB 和参数。`w4194–4368` 表明第一个 uint 的高字节归一化为 `r`，RGB 通道恢复后平方成为本段基色 `C`。这里是选定 shader 内部的转换，不能据此断言整个管线严格采用某个标准 sRGB 传递函数。

`L` 来自 `FrameConstants.dir_to_primary_directional_light`（`w4478–4483`）；`V` 为重建视线的反方向（`w4574–4588`）；`H=normalize(L+V)`。在未选中材质特殊分支时，本段可重组为：

```text
cL = clamp(dot(N,L), 0, 1)
cV = max(dot(normalize(N),V), 0.0001)
cH = clamp(dot(L,H), 0, 1)
k = 2*r²*cH² - 0.5
diffuse = C/π * (1+k*(1-cL)^5) * (1+k*(1-cV)^5)
```

定位：`w6476–6531` 的方向项，`w6566–6666` 的两组五次幂与 `1/π`。这是 **Disney/Burley 型粗糙漫反射的结构对应判断**，不是原作者给出的算法名称。材质控制位还会改变它：所选高字节的 bit 6 为真时，`w6545–6559` 把这一路 `cL` 改为 `0.2+0.6*cL`；不能把特殊分支叫作所有砖、草、树共同的默认公式。

`w6679–6967` 另有微表面高光：原始 `dot(N,L)` 或 `dot(N,V)` 不大于零时该高光分量为零；否则使用如下核心项：

```text
a2 = r^4
D = a2 / (π * (dot(N,H)^2*(a2-1)+1)^2)
F = 0.04 + 0.96*max(0,1-dot(H,L))^5
G = 2*NL*NV /
    (NL*sqrt(NV²*(1-a2)+a2) + NV*sqrt(NL²*(1-a2)+a2))
specular = D*F*G/(4*NL*NV)
```

其中 `NL`、`NV` 是这段重新计算的原始点积；不要用上面的受特殊材质修正值替换。形式对应 GGX 分布、Schlick Fresnel 和相关 Smith 遮蔽。它与漫反射相加后，再乘太阳色、衰减和角度。控制位 bit 2 为真时，`w7000–7009` 再乘本段可见性 `visibility=(1-contactTerm)*screenShadow.r`；`screenShadow.r` 的实际读取在 `w6457–6466`。本轮没有完整恢复 `contactTerm` 之前的所有求解过程。

**构造演算。** 面向光源与相机，`NL=NV=dot(N,H)=dot(H,L)=1`、`r=0.8`、无特殊位时，漫反射为 `C/π`；`a2=0.4096`，`D≈0.7771`、`F=0.04`、`G=1`，高光约 0.00777。最终还会乘光色/可见性并叠其他光照，不能把这个局部结果当截图颜色。

天空、屏幕间接光、`indirect_radiance_tex`、灯光网格/采样 reservoir 等仍在同模块的其他范围中；`w11319` 已将一组直接与间接结果相加，之后还有灯光和 debug 分支。**本篇没有恢复完整 GI、灯笼重采样或最终后期色彩链。** “用了 GGX”也不能单独解释整幅画面的美术风格。

## 级联到柔影的实际步骤

119 已确认选定 CPU 调用请求 3 层、每层边长 1024。新的 compute 证据补齐接收端过滤，而非再次估算层数：

| 步骤         | 选定指令                   | 可确认行为                                                                                                    |
| ------------ | -------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 选择级联     | `w3920–3972`               | 读取 split 向量，依次比较接收点的深度量并选层；矩阵读取使用同一层号                                           |
| 接收点修正   | `w4041–4139`               | 按投影、texel 尺度、法线与光向夹角构造偏移，存在 `max(0.1,abs(dot(...)))`；不是一个对所有距离都相同的世界偏移 |
| 搜索遮挡者   | `w4279–4631`               | 循环上限 8；以旋转散布位置取原始 shadow-map 深度，`referenceZ > sampledZ` 才进入累计分支                      |
| 极端结果退出 | `w4324–4332`、`w4639–4653` | 累计数为 0 或 8 时分别进入可见性 1 或 0 的局部结果，跳过后面的比较采样循环                                    |
| 调整过滤范围 | `w4657–4703`               | 使用累计深度/数量、接收点和投影量推导半影范围，并限在两个尺度之间                                             |
| 比较采样     | `w4710–4975`               | 另一循环上限 8；`w4938` 是实际 `OpImageSampleDrefExplicitLod`，同时累积可见性的一阶、二阶矩                   |

这与 **PCSS 式“先找遮挡者，再调 PCF 范围”** 相符，是基于计算结构的归类。本轮不把它宣称为某个标准 PCSS 实现逐行一致。原始深度比较与采样器比较也有自己的约定，不能因为主相机使用反向深度就直接倒置这里的条件。

最多 8+8 次是**进入该工作分支的单 invocation 循环上界**，不是所有屏幕像素固定 16 次；前面还有分组/材质筛选，0/8 极端情况也提前退出。静态采样指令只有一个循环站点，并不表示只采一次。

## 柔和也依赖时域限幅

比较采样得到均值 `m` 和二阶矩 `m2` 后，`w4997–5067` 计算：

```text
sigma = sqrt(max(0,m2-m*m))
window = m + (-1,+1) * sigma * 3 * max(0,1-0.2*radius)
```

`w5072–5167` 读取重投影纹理。只有**重投影第三通道 >0、`history_valid!=0` 且 `frame_counter.index!=0`** 的选定分支才选用采样历史，否则以当前均值代替历史。随后历史先 clamp 到上述区间，再在 `w5252` 混合：`result=0.875*clampedHistory+0.125*m`。后面还有输出范围/统计等处理，不能把中间 window 当最终阴影值。

**构造演算。** 若 `m=0.6`、`m2=0.4`、`radius=2`，则 `sigma=0.2`、window=`[0.24,0.96]`。有效历史为 1 时先压到 0.96，再得到 0.915；无有效历史时这一混合仍为 0.6。演算说明历史为什么既稳定又可能滞后，不证明原作移动编辑时一定无拖影。

## 借鉴与边界

综合 demo 可先采用 URP 的主光、现成软阴影和可控环境光，保留相同材质家族的粗糙度、法线、调色规则。自定义屏幕柔影若以后确有需求，再把遮挡者搜索、过滤分辨率、历史失效和编辑区刷新作为一个独立预算；不能只移植“历史权重 0.875”而省掉运动/深度拒绝及限幅。

[lighting_wind_water_probe.py](tiny-glade/tools/lighting_wind_water_probe.py) 本轮回读上述关键指令、常数与 native 锚点；原始解析/反汇编和新回执在 ignored `.cache/procedural-modeling/tiny-light-wind-water/`。通过的是选定静态锚点和结构读取，不是完整反编译、`spirv-val`、GPU 执行或性能验收。全部画面、真实帧耗时和 Unity 适配 **Not Run**。
