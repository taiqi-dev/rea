# 07 身体材质、贴图与形态感知花纹

[目录](README.md) · [编辑重建](06-editor-input-and-rebuild.md)。关键是把两件事分开：**花纹在三维身体上怎么走**，以及**绘制结果存在哪块二维贴图里**。这样不同腿数、长短和粗细不必使用固定人形 UV。

## 已有证据

后续[35专项研究](35-skin-pattern-shape-edits-and-seams.md)补查身体加宽、肢体拉长和新增部件，并完整读取开发者皮肤章节及脚注7：裙边多边形是原型，最终发行版禁用裙边、保留纹理扩张。它还补固定社区格式引用链及独立密度/锚点/相位/接缝算法。本页算法仍是独立基础规格，不能据此声称原作的编辑重绘策略已恢复。

公开事实摘要和来源见 00。Maxis 的生物皮肤资料支持表面粒子笔刷与 base/coat/detail 分层；开发笔记解释快速 charting 与接缝处理。早期原型和后来系统存在差异。车辆/建筑的运行时映射不能拿来证明生物使用三平面贴图。

本机 EXE 的有界 ASCII 检查支持以下词汇存在。偏移为原始文件偏移；没有交叉引用，不等于活跃脚本。

| 类别 | 原始词汇与偏移 |
| --- | --- |
| 系统 | `Swarm/SkinPaint` 0xff19f4；`Skinner/Swarm` 0xff1a48；`Skinner/PaintSystem` 0xff81a8 |
| 区域 | `bodyRange` 0xff1908；`belly` 0xff1914；`back` 0xff191c；`joints` 0xff1924；`limbs` 0xff1934；`torso` 0xff193c |
| 形态位置 | `limbType` 0xff1bfc；`limbPos` 0xff1c08；`torsoPos` 0xff1c10；`boneOffset` 0xff1c1c；`bonePos` 0xff1c28；`boneAngle` 0xff1c30 |
| 通道 | `specularAlpha` 0xff1c9c；`bumpAlpha` 0xff1cbc；`diffuseAlpha` 0xff1cd4 |
| 笔刷 | `restrict` 0xff21a8；`attract` 0xff21b4；`initDir` 0xff21bc；`align` 0xff21c4；`curve` 0xff21cc；`brush` 0xff21ec |
| 骨链方向 | `alongspine` 0xff26f0；`aroundspine` 0xff26fc；`alongbone` 0xff2708；`aroundbone` 0xff2714 |

区域读取窗口包括 `[0xff1840,0xff1960)`、`[0xff1bc0,0xff1d70)`、`[0xff20c0,0xff2200)`、`[0xff26b0,0xff2770)`；系统名称另来自 `.rdata` 有界字符串表。`paintTheme` 无命中不证明没有主题。Terrain 邻域的 BrushTexture 和星球可视化的 cubemap 名称不作为身体皮肤证据。

## 独立规格：结构、输入、输出

以下类型、阈值、积分方法、混合和失效规则由我们独立定义；它们不能逐像素复制原游戏。

```text
SurfaceMesh { vertices[], triangles[], adjacency[], skeletonWeights[] }
SurfaceFrame { position, normal, tangent, binormal, semanticBodyCoords }
SurfaceWalker {
    triangleId, barycentric, tangentDirection
    age, lifetime, randomState, scriptId, sourcePartId
}
PaintRecipe { layers[Base, Coat, Detail], palette, seed }
UVAtlas { cornerUVs[], chartIdOfTriangle[], packedRects[], revision }
MaterialMaps { color, specular, bumpHeight, optionalMasks }
BakeKey { shapeRevision, paintRevision, assetDigests, ownQualityProfile }
```

粒子附着在表面三角形上，用重心坐标定位。它的沿肢体方向来自形态坐标框架，和图集上的 x/y 无关。图集可以将同一条腿切成多块，粒子仍沿三维表面走。

## 自研算法 A：生成可绘制的 UV

独立 chart 策略选择六向轴分区；阈值和打包器是我们的配置，不是原游戏参数。`cos(30°)` 仅为示例。

```text
MakeOwnAtlas(mesh):
    validate triangles are finite and non-degenerate
    unassigned = all triangles in stable ID order
    charts = []
    while unassigned.notEmpty:
        seed = unassigned.first
        axis = nearestAxis(seed.normal, {+X,-X,+Y,-Y,+Z,-Z})
        chart = floodAdjacent(seed, accept face where:
            face is unassigned and dot(face.normal, axis) >= cos(30 degrees))
        project chart vertices onto plane perpendicular to axis
        reject chart if projected area collapses or overlap violates own policy
        charts.append(chart with padded boundingRectangle)
        unassigned.remove(chart.faces)
    layout = OwnRectanglePacker(charts, maxAtlasSize)
    if layout.failed: return Error(AtlasCapacityExceeded, layout.details)
    return corner UVs transformed by each chart rectangle
```

种子顺序和投影规则会改变 chart 数量。上面没有声称恢复游戏随机种子、投影阈值或精确打包方式。UV 保存在三角形角点而非仅顶点，才能让共享空间顶点在不同图块拥有不同 UV。

## 自研算法 B：区域分布与表面运动

我们可把脚本输入定义为：区域谓词、初始方向、生命周期、密度、颜色和笔刷尺度。区域谓词依据身体框架，如躯干局部上下、距关节的形态距离；这不是原作区域分类公式。

```text
PaintOwnCreature(mesh, atlas, recipe, bodyFrames):
    maps = AllocateOwnMaps(qualityProfile.resolution)
    rng = OwnSeededGenerator(recipe.seed)
    for layer in [Base, Coat, Detail]:
        script = recipe.layers[layer]
        walkers = SampleEligibleSurfaceByArea(mesh, script.regionPredicate,
                                             script.density, rng)
        for fixedStep in 1..script.stepBudget:
            for walker in alive(walkers):
                frame = EvaluateBodySurfaceFrame(walker, bodyFrames)
                desired = script.direction(frame, walker.randomState)
                tangent = desired - dot(desired, frame.normal)*frame.normal
                step = NormalizeOrDiagnose(tangent) * script.speed * ownDt
                walker = AdvanceAcrossAdjacentTriangles(walker, step)
                if walker.failed: record PaintPathFailed; stop that walker
                footprint = CollectAdjacentBrushTriangles(walker,
                                                         script.brushRadius)
                RasterizeOwnBrush(footprint, atlas, maps, script)
    PadChartBordersByOwnPolicy(maps, atlas)
    BuildOwnMipChain(maps)
    return ValidateAndBakeOwnMaterial(maps)
```

跨面运动需要找到步进线段与当前三角形边的交点，进入相邻面后更新重心坐标，并把切向方向重新投到新面。超过单步跨面预算时细分步长或返回失败。不能用“找最近三角形”无条件跳过去，那可能从一条腿跳到相邻另一条腿。

## 自研算法 C：三维笔刷写入二维图集

同一三角形的表面点和 UV 通过相同重心权重关联：

```text
p  = b0*p0  + b1*p1  + b2*p2
uv = b0*uv0 + b1*uv1 + b2*uv2
b0+b1+b2 = 1
```

例：p0=(0,0,0)、p1=(1,0,0)、p2=(0,1,0)，UV 为 (0.1,0.1)、(0.5,0.1)、(0.1,0.5)，b=(0.2,0.3,0.5)，则 p=(0.3,0.5,0)，uv=(0.22,0.30)。一个 UV 像素对应一个表面位置，再在笔刷自身三维框架中采样。

```text
RasterizeOwnBrush(footprint, atlas, maps, brush):
    for triangle in footprint:
        for pixel in RasterizedUVTriangle(triangle.cornerUVs):
            bary = BarycentricAtUV(pixel)
            p = InterpolateSurfacePosition(triangle, bary)
            brushCoord = inverse(brush.worldFrame) * p
            alpha = brush.texture.sample(brushCoord) * brush.opacity
            maps.color[pixel] = lerp(maps.color[pixel], brush.color, alpha)
            maps.specular[pixel] = OwnSpecularBlend(oldValue, brush, alpha)
            maps.bumpHeight[pixel] = OwnHeightBlend(oldValue, brush, alpha)
```

这是自研混合定义。颜色需明确在线性空间混合；凹凸高度和高光的合成规则不可直接等同颜色插值。高度转法线可用纹理梯度与切线基，实际单位、通道布局与原游戏规则未知。

笔触跨 UV 接缝时，同一个三维范围会同时绘制多块图集区域。绘制完扩张图块边缘，为双线性和 mip 采样提供有效邻域；padding 大小要按我们的 mip/压缩政策设计。仅让粒子沿 atlas 中一条二维直线行走，会跨到错误部位。

## 花纹怎样随身体变化

独立例：40 cm 腿每 10 cm 一组环纹，得到 4 组；腿变成 80 cm，保持物理密度得到 8 组，保持相对数量仍为 4 组。这是两种不同产品政策。`alongbone/aroundbone` 支持研究相对坐标，但不证明原游戏所有花纹固定密度或固定数量。

身体编辑改变当前表面和形态框架，需要更新花纹布局或按明确规则重投影。通常的固定拓扑蒙皮动画只移动顶点及切线，UV 可保持，贴图随皮肤运动；这是一般图形学关系，不能据此确认原游戏每项编辑的烘焙时机。06 的版本政策是我们的选择。

材料不仅是颜色：相同颜色在不同高光、法线、光照下呈现不同质感。AO 用于局部遮蔽外观，不能替代全部动态照明。历史公开实现提到 AO 烘焙，但本机样本数、分辨率、贴图压缩与刷新策略未恢复。

## 未知与验证边界

实际配方见[36](36-selected-skinpaint-recipe-and-material-controls.md)：取得选定主题、条纹和区域分布的配置/引用，仍没有恢复表面运动、笔刷内容或编辑刷新。不能用这条新增静态路径扩大本页原先的文字/名称验证范围。

几何接缝与UV接缝的进一步区分见[29](29-creature-mesh-joins-and-automatic-skinning.md)：UV拆点必须共享逻辑位置与最终蒙皮权重；图集padding修复采样边缘，不能修复运动后分离的两张网格。29补充了原作权重来源的历史说明，精确生成和平滑公式仍未知。

未知：具体脚本资源、种子、采样密度、区域公式、跨面方向算法、笔刷尺度、UV 阈值和打包器、通道混合、预制部件接缝、AO 参数、纹理尺寸、缓存失效时机。

已检查：公开文本与本机名称、摘要；重心算例见 09。未做：脚本解码、反编译、PDF 截图视觉核验、原游戏像素对照或 bake 性能测试。风险：自研完整流程不能认作发行版渲染管线。
