# Tiny Glade：窗台与窗周自动装饰的生成和更新

窗户生产与变化发布见 [16](16-tiny-glade-window-placement-and-holes.md)，墙体重建见 [17](17-tiny-glade-window-wall-reconstruction.md)，模型标记变换见 [18](18-tiny-glade-window-frames.md)，原始证据与复核范围见 [20](20-tiny-glade-window-evidence-ledger.md)。本篇从候选追到区域、随机选择、碰撞排除和实体请求生命周期。

已确认两条入口汇合到稳定键的 pending 请求：窗台候选直接转请求；窗周围先生成定向矩形区域、局部采样和重叠筛选，再转请求。实体按键复用，淘汰采用待删除标记。

证据：matched EXE/PDB；26 个精确符号范围、71414 B 线性解码。解码完整不代表控制流全部可达。PDB路径/名字仅用于入口身份，算法规则来自具体指令。REA provider不可用，本交付是带provenance的静态fallback，不是REA Evidence或反编译。

EXE SHA256 `4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5`。PDB身份复用 `../tinyglade-symbols/identity.json`；所有字节范围/摘要见本机 `tinyglade-windows-clutter/findings.json`，证据链接见 20。

## W01 窗台候选转请求

WindowAutoClutterCandidate 是 0x50 B 记录，输入向量被 drain；6 为终止哨兵。raw tag 0..5 在跳转表选择 mesh/reference，之后统一追加 0x68 B pending 请求：+40=输入+40稳定键，+48/+50=输入+20/+28位置，+54=float3法线，+60=1.0；本函数没有 RNG 调用或碰撞筛选，也没有创建 ECS 实体。

依据 E01, E02, E03，精确地址表见文末。

与 18 的实际生产者对齐：cottage 的 `0x8C97BC–0x8C980C` 追加 tag1 的 80B 记录，其 `+0x10..+0x3F` 是 flowerbed marker Transform，`+0x40` 是窗 ID、`flower_bed` 字串与 marker 序号组合的稳定键。此处同一布局的 tag1 分支消费资源索引、位置和四元数，因此已贯通 marker → 窗台请求。候选并未在该函数内执行窗周区域的碰撞贪心筛选。

## W02 窗台法线与 cottage tag1 对齐

输入 quaternion q=(x,y,z,w) 旋转 e_z，法线 n=(2xz+2wy, 2yz-2wx, w²-x²-y²+z²)。tag1 以 input+8 从资源 bundle+8 向量选择 mesh；tag2 特殊请求字节=((~input+1)&1)，保留 input+4；其他分支写字节2并清零+34。input scale 未在此复制，请求+60总写1。外部 cottage 生产者的 flowerbed_xforms 与 +40稳定hash，见 18 的生产端证据，不能仅凭本callee给出上游生成概率。

依据 E04, E05。

## W03 窗周围入口和资格

DecoratorType::spawns_clutter 实际规则为 unsigned raw tag<2。around_windows 对 PublicWall+258 的u32>1跳过；装饰kind 0/1走普通分支，kind2仅 subtype byte5或10通过。字段/枚举的原始语义尚未恢复，不能把这些raw tag命名为所有游戏UI窗类型。

依据 E06, E07。

## W04 普通窗的双侧矩形

普通分支从墙曲线找到线段i/t，T=lerp(Pi,Pi+1,t)的XZ；d=normalize(Pi+1-Pmax(i-1,0))的XZ，非法逆长度则d=0；n=(-dz,dx)。两个方向矩形尺度e=(4,2)，中心 T±2.36d+1.28n，原点 o_right=T+0.36d+0.28n、o_left=T-4.36d+0.28n；y取装饰记录的float。键分别 hash(("decorator_right",windowID,generation_u32))、hash(("decorator_left",windowID,generation_u32))。两区域+38均写0、+39复制另一装饰byte、+34复制windowID。曲线定位 helper 的完整弧长语义未在本报告恢复。

依据 E08, E09, E10。

## W05 kind2的双区域

通过 subtype 限制后的kind2分支使用 cached decorator transform，d=quat旋转e_x的XZ。两个区域中心=T_xz±1.45d，y=T_y+0.5，e=(1.5,1.5)，原点=center-0.75(d+n)，n=(-dz,dx)。stable key=hash(("trap_door",sideIndex,windowID,generation_u32))，sideIndex0/1；+38写1；这不是断言游戏中所有trap door一定产生装饰。

依据 E11, E12。

## W06 矩形区域更新与局部重采样

AutoClutterState regions hash bucket=0x48 B(key8+value64)。add_region对几何float value+18..+30、u32+34、byte+38/+39逐项有序相等检查，NaN视为改变。未改变仅刷新 epoch value+3c。改变时从旧Rectangle2d/AABB覆盖格移除ID，将ID登记进新覆盖格；有效旧u16 index排入删除队列，新64B region覆盖旧值，epoch刷新后立即flush。新输入两窗路径都带index FFFF。仅比较列出的字段，未比较owner枚举payload全部内容。

依据 E13, E14, E15。

## W07 局部tile订阅与失效

autoclutter_subscribe_to_tabloids 订阅RaycastWorld raw classes 0,1,3,4,5,6,7,2，并存Subscriber，另有Publisher/WorldRaster/PlantSampleRaster订阅。populate take这些DirtyTiles并extend合并；iter_tiles通过 state grid tile→Vec<regionID>，把region有效索引<=FFFD加入删除队列并置FFFF。populate随后flush并只采样FFFF项，先置FFFE；接受时才写实际candidate索引。实际 wall/window 事件发布到这些class的上游触发与scheduler顺序未完全追踪。

依据 E16, E17, E18, E19, E20, E21。

## W08 稳定采样和加权类型选择

位置RNG初始化于 hash(IVec3(saturating_trunc(2*origin_xyz)))；类型RNG以 hash((regionID,0)) 初始化。在非Halloween、raw subtype byte0的实指令分支，9个resource pointer对应weights=[1.2,1.2,2.5,1,1,1,1,s,1]，其中s=1.5当region+38!=1，否则0；各资源+30==-1时对应weight归零。求W=sum(weights)，随机u=f32(RNG)，累计wi/W，选择首次严格大于u的槽，越尾fallback槽0；W=0等退化不能凭正常公式概括。其它subtype的weights不同，未全恢复；s不能独立命名为empty概率或密度。

依据 E22, E23, E24, E25。

## W09 区域内位置：边距与周期包裹

region+38<2分支：a=region+18方向二维，n=(-a1,a0)，e=region+20/+24，p=region+28/+30的XZ；m=chosen resource+60。p′=p+m(a+n)，e′=max(e-2m,0.01)逐分量；U=(RNG_f32,RNG_f32)，q=U⊙e′-p′；v=(q·a,q·n)/e′；f=v-floorf(v)；sampleXZ=p′+a*(f0*e′0)+n*(f1*e′1)。floorf经PE import trampoline确认，不能替成clamp。unit方向下位置在收边矩形内；退化d=0不保证此结论。

依据 E26。

## W10 环境与候选间排除

populate 使用向下raycast/terrain fallback得到高度，且有Rectangle3d形状碰撞、墙/曲线/植被相关条件分支；本报告未把所有inlined条件归属到具体环境mask。process首先按candidate+40稳定键排除输入HashSet成员；候选按(u32 candidate+90, u64 regionID+88)降序，普通窗路径+90来自windowID。依次测试与已接受Rectangle3d重叠，重叠跳过；raw candidate+30=6绕过本次重叠检测，仍把自身box加入已接受表。Rectangle3d helper先检查闭合y区间交叠，随后tailcall2D矩形交叠。窗口台请求不经过此函数的这套候选box筛选。

依据 E27, E28, E29, E30, E31, E32。

## W11 旧候选swap-remove

flush_candidates_pending_removal将u16索引的0x98 B候选移走，尾元素填补该位置、len--；若移动了尾元素，用其+88 regionID查对应region，要求旧u16 index=old_last_index并<FFFE，再写新index。无mapping或索引不一致走panic而不是静默忽略。pending长度最终清0。多删除索引的排序helper存在，本报告未恢复其比较规则；构造演算只用一个删除索引。

依据 E33。

## W12 过期region与实例生命周期

remove_stale_regions 的实指令 retain：entry epoch=value+3c若等于state+90则保留，否则从lazy grid移除、有效candidate排入移除队列、regions表擦除。manager以pending请求+40键构建map，再扫描没有ClutterMarkedForDeletion的AutoClutter实体；同键的特殊状态分支直接复制目标position并生成orientation写Transform，另一分支比较目标/旧position距离，<=0.1保留，>0.1走待删除。找不到key也排入 ClutterMarkedForDeletion 命令。未已有key的请求有近实体距离 gate，符合条件才reserve_entity并排队spawn<AutoClutter>；队列的真正apply、mesh最终消费者/动画/despawn未追到底。

依据 E34, E35, E36, E37, E38, E39, E40, E41。

## 数据记录（offset解释均基于实指令）

|记录|已核对布局|
|---|---|
|WindowAutoClutterCandidate（80B）|+0 tag、+1 byte、+4 u32、+8 resource index、+10 quaternion、+20 position、+40 stable key、+48 payload|
|AutoClutterRegion（64B）|+0 owner enum/payload、+18 direction、+20/+24 extent、+28/+2c/+30 origin xyz、+34 sort u32（窗路径=windowID）、+38 placement flag、+39 category byte、+3a u16 candidate index、+3c epoch|
|AutoClutterCandidate（152B）|+40 stable key、+68 32B Rectangle3d、+88 regionID、+90 sort u32|
|Pending request（104B）|+38 resource pointer、+40 stable key、+48 position、+54 orientation normal、+60 scalar|
|AutoClutterState|+8 lazy-grid vector、+20 candidate ptr/+28 len、+38 removal ptr/+40 len、+50 request ptr/+58 len、+60 regions table/+78 len、+90 epoch|

## 构造演算 X1：同一普通窗的两个周围区域

这些是人为输入的状态/算式演算，不是运行时复现。

```json
{
  "id": "X1",
  "status": "constructed_not_runtime",
  "scenario": "同一普通窗的两个周围区域",
  "input": {
    "windowID": 42,
    "generation": 7,
    "T_xz": [
      10,
      0
    ],
    "d": [
      1,
      0
    ],
    "height": 3
  },
  "output": {
    "right_origin": [
      10.36,
      0.28
    ],
    "left_origin": [
      5.64,
      0.28
    ],
    "right_center": [
      12.36,
      1.28
    ],
    "left_center": [
      7.64,
      1.28
    ],
    "extent": [
      4,
      2
    ],
    "region_flags": 0
  },
  "interpretation": "双稳定key由同一窗ID和generation加不同literal区分。每区至多保存一个当前候选索引，不保证两个候选都接受；候选数量不能直接等同最终模型或实体数量。"
}
```

## 构造演算 X2：X1右区域内采样

这些是人为输入的状态/算式演算，不是运行时复现。

```json
{
  "id": "X2",
  "status": "constructed_not_runtime",
  "scenario": "X1右区域内采样",
  "input": {
    "p": [
      10.36,
      0.28
    ],
    "a": [
      1,
      0
    ],
    "e": [
      4,
      2
    ],
    "m": 0.1,
    "U": [
      0.25,
      0.75
    ]
  },
  "intermediates": {
    "p_prime": [
      10.46,
      0.38
    ],
    "e_prime": [
      3.8,
      1.8
    ],
    "q": [
      -9.51,
      0.97
    ],
    "v": [
      -2.5026315789473683,
      0.5388888888888889
    ],
    "fract": [
      0.4973684210526317,
      0.5388888888888889
    ]
  },
  "sample_xz": [
    12.35,
    1.35
  ],
  "interpretation": "使用floorf的fract，将负局部坐标包裹回矩形，非clamp。未断言真实RNG输出为这些值。"
}
```

## 构造演算 X3：raw subtype0 weighted选择

这些是人为输入的状态/算式演算，不是运行时复现。

```json
{
  "id": "X3",
  "status": "constructed_not_runtime",
  "scenario": "raw subtype0 weighted选择",
  "input": {
    "all_nine_resources_available": true,
    "region_flag": 0,
    "u": 0.3
  },
  "weights": [
    1.2,
    1.2,
    2.5,
    1,
    1,
    1,
    1,
    1.5,
    1
  ],
  "weight_sum": 11.4,
  "selected_slot": 2,
  "selected_resource_bundle_offset": "0x18",
  "interpretation": "累计槽0=.105263、槽1=.210526、槽2=.429825，u=.30选slot2；仅此raw subtype/季节分支，不将其资源命名具体物件。"
}
```

## 构造演算 X4：窗移动导致region index0重采样

这些是人为输入的状态/算式演算，不是运行时复现。

```json
{
  "id": "X4",
  "status": "constructed_not_runtime",
  "scenario": "窗移动导致region index0重采样",
  "input": {
    "candidates": [
      "window-right",
      "window-left",
      "unrelated-region"
    ],
    "region_indices": {
      "right": 0,
      "left": 1,
      "unrelated": 2
    },
    "pending_remove": [
      0
    ],
    "right_origin_before": [
      10.36,
      0.28
    ],
    "right_origin_after": [
      11.36,
      0.28
    ]
  },
  "output": {
    "candidates_after_flush": [
      "unrelated-region",
      "window-left"
    ],
    "region_indices_after_flush": {
      "right": "0xffff",
      "left": 1,
      "unrelated": 0
    }
  },
  "interpretation": "add_region旧索引0排队，新region带FFFF；swap-remove搬尾2至0并修正其region索引。新right先置FFFE后采样；成功写新index，失败留FFFE。旧entity可能更新或mark deletion，须经manager条件判定。"
}
```

## 未知与未做

- 未恢复PDB类型字段，raw enum及resource slot的游戏UI类型/物件名未知。不得根据函数名给+50权重槽命名empty。
- 环境filter_clutter_object大量内联条件只核对局部，不提供所有类型的墙/道路/水/植物阈值或密度闭式。
- 墙变形/窗移动到WorldRaster/RaycastWorld publisher的精确事件链未全贯通；add_region几何更新、dirty-tile局部invalidate和过期retain已确认。
- epoch何时增加、这些systems实际调度顺序和执行频率未确认；函数直接call不能当作全局每帧顺序。
- spawn/insert均为deferred command queue，最终mesh、visibility、动画/删除consumer和提交时刻未知。
- cottage flowerbed上游候选概率见 18 的生产端；其全部概率仍未恢复；on_windows本函数只搬运，不足以推上游有多少盆花。
- 多删除索引排序与repeat/duplicate处理未恢复；只给单移除构造演算。
- REA provider/MCP不可用沿用静态fallback；没有执行游戏、读取存档、运行时复现或反编译。

风险：偏移布局和分支规则有实字节支持；字段命名、所有环境mask、全局调度和最终渲染仍不完整。未携带游戏资产或恢复代码进入生产项目。

## 关键证据范围

| ID | RVA（结束不含） | 文件 offset | 说明 |
| --- | --- | --- | --- |
| E01 | 0x28e9c81–0x28e9d08 | 0x28e9081 | 向量 drain 与资源地址 |
| E02 | 0x28e9d20–0x28e9dea | 0x28e9120 | 0x68请求写入、0x50步长、tag6 |
| E03 | 0x28e9df5–0x28e9f5c | 0x28e91f5 | raw tag分支和quaternion旋转 |
| E04 | 0x28e9df7–0x28e9e1e | 0x28e91f7 | tag1 indexed mesh与tag4 |
| E05 | 0x28e9e1e–0x28e9f43 | 0x28e921e | 旋转公式与flag归一 |
| E06 | 0x9012d0–0x9012d8 | 0x9006d0 | cmp rcx,2;setb |
| E07 | 0x28edd08–0x28ede7b | 0x28ed108 | 墙资格、装饰tag、kind/subtype分支 |
| E08 | 0x28ee18e–0x28ee2b1 | 0x28ed58e | 曲线点选择、归一化与key |
| E09 | 0x28ee2b1–0x28ee498 | 0x28ed6b1 | 第一矩形几何与4,2 |
| E10 | 0x28ee4a8–0x28ee5ec | 0x28ed8a8 | 第二矩形；两者flag0 |
| E11 | 0x28ede5b–0x28edf3b | 0x28ed25b | cached transform、y+.5、orientation |
| E12 | 0x28edf50–0x28ee105 | 0x28ed350 | ±1.45、1.5矩形、两个key/region |
| E13 | 0x10d006c–0x10d0116 | 0x10cf46c | float和标志比较 |
| E14 | 0x10d0194–0x10d0377 | 0x10cf594 | 旧格移除、新格登记、旧candidate排队、覆盖 |
| E15 | 0x10d0537–0x10d054e | 0x10cf937 | epoch与flush |
| E16 | 0x28e639c–0x28e6570 | 0x28e579c | 八种RaycastWorld订阅 |
| E17 | 0x28e658d–0x28e676d | 0x28e598d | 其他订阅 |
| E18 | 0x28dc094–0x28dc177 | 0x28db494 | take/extend/tile invalidation/flush |
| E19 | 0x21a6436–0x21a6575 | 0x21a5836 | tile→regionID→pending indices与FFFF |
| E20 | 0x28dc540–0x28dc5c2 | 0x28db940 | 仅FFFF进入采样；先FFFE |
| E21 | 0x28dff02–0x28dffb5 | 0x28df302 | 接受写index、regionID/windowID排序字段 |
| E22 | 0x28dc59b–0x28dc66f | 0x28db99b | 位置quantization与RNG seed |
| E23 | 0x28dcb50–0x28dcd93 | 0x28dbf50 | category0九槽weights及资源条件 |
| E24 | 0x28dce2a–0x28dce77 | 0x28dc22a | regionID,0类型seed与tag分支 |
| E25 | 0x28dcef0–0x28dcfd5 | 0x28dc2f0 | sum、RNG、累计归一选择 |
| E26 | 0x28dcfd5–0x28dd0d6 | 0x28dc3d5 | 采样、边距、0.01下限、投影/fract/re投影 |
| E27 | 0x28dd1e5–0x28dd25f | 0x28dc5e5 | 向下ray和terrain fallback |
| E28 | 0x28dfe42–0x28dfef1 | 0x28df242 | shape overlaps boolean分支 |
| E29 | 0x21a8a50–0x21a8c10 | 0x21a7e50 | key排除和OrderedCandidate构造 |
| E30 | 0x219ef1b–0x219ef82 | 0x219e31b | 降序priority/regionID |
| E31 | 0x28ea311–0x28ea3b5 | 0x28e9711 | 重叠greedy与type6例外 |
| E32 | 0xdf3f80–0xdf3f9d | 0xdf3380 | 闭合Y区间+2D tailcall |
| E33 | 0x10d07af–0x10d0941 | 0x10cfbaf | swap remove和moved region index校验 |
| E34 | 0x219cf9a–0x219cfa4 | 0x219c39a | epoch retain条件 |
| E35 | 0x219d099–0x219d17c | 0x219c499 | 删grid、candidate排队、擦region |
| E36 | 0x28eb5fa–0x28eb665 | 0x28ea9fa | same-key Transform update |
| E37 | 0x28eb809–0x28eb89c | 0x28eac09 | 距离阈值/absence与delete command |
| E38 | 0x28d9330–0x28d9379 | 0x28d8730 | 唯一PDB/指令 deletion command closure |
| E39 | 0x28ebd77–0x28ebde0 | 0x28eb177 | 新请求近实体距离gate |
| E40 | 0x28ec157–0x28ec2c2 | 0x28eb557 | reserve entity与spawn命令写入 |
| E41 | 0x28d96c0–0x28d9712 | 0x28d8ac0 | 唯一spawn AutoClutter closure |
