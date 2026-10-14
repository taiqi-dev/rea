# Tiny Glade 树资源加工与实例发布

## 结论

extract_canopy/extract_trunk并非本轮PDB中的独立函数，它们是build_prefab(C53680，18943B)内部按名字选择的CPU分支。树冠留下Vertex_Color.B<=0的顶点，树干留下B>0的顶点；过滤后的indices逐项压缩，所有属性按同一资格筛选，再用旧→新vertex编号改写剩余indices。树冠按原prim_center的三个float32位模式分组，累加Vertex_Normal并归一化后广播为prim_normals；同时把prim_center改成组内Vertex_Position条目的算术均值。已有appear_pos/age保留；缺失时分别补(0,0,0)及1。

发布侧另已证spawn_prefabs→atlas lookup→逐条创建实例：16B GpuInstance和48B PlacementData写到相同dense索引，并更新待上传的min/max范围。**processed mesh具体怎样成为atlas meshID、本轮CPU staging怎样真正传到GPU尚未贯通。** 不借用砖的上传证据、不把图中断点补成强关联。

所有地址是CPU RVA。固定EXE/PDB SHA再次匹配4627ec9f9a8abe03dd30751f6a8e22868e0dfddf9f40029a1b848a3773495fe5 / ca8b5f18fcf5a79e282db9af9178b6ec8cecb776ea41f68435b543079d34dcf2。选定15个native范围共42213B全部线性解码；未运行/附加游戏、读存档、改原文件、安装或构建。原模型只保存统计/hash，不导出几何。本轮正式文档只创建61。

## 1. 源资源到加工分支

上轮56已经确认default.ron引用两种processor和树干/冠shader，branchy1两部分用同一branchy_tree_v1；mid1分别用mid_distance_tree_v1和_trunk。本轮从EXE里的extract_指令立即数与prim_normals引用找到真实producer，随后完整解码build_prefab，核实名称长度14/13及字节比较，不能只据配置名称猜算法。

C53FA4–C53FDC匹配extract_canopy，C53FFD实际call1824F90；C54144–C54165匹配extract_trunk，C54186实际call18255C0。其前C53DE8调用load_json_as_mesh，C53CBA与C55522使用以(mesh_name, optional MeshProcessorConfig)为key的缓存；加工后mesh进入Arc缓存。源同名而processor不同，不应该在研究规格中合成一个缓存对象。

build_prefab随后C55F2D扩大PrefabPart数组，load_prefabs_impl在C58DB6调用build_prefab，C58F3B将Prefab插入库。这里已证调用与容器，未恢复PrefabPart全部字段到atlas建立过程；因此这段连接强度弱于split/属性加工。

## 2. 颜色资格、属性压缩与编号

1824F90先查Vertex_Color并以as_f32x3取得每顶点三float；1825310–182535C的SIMD和1825389/18253B3的尾项都把B<=0编码为1。18255C0的182596C/18259B6分别用0<B和B>0，故树干strict，不含0。有限输入下二者互补；NaN两边均不取，不从有限分类外推NaN处理。

18253E6/1825A1E调用Mesh.retain_vertices(A97000)。A97050–A9713A逐条indices检查mask[oldIndex]==1，丢弃不符条目并保持其他次序；**不是显式以三个index为一组删整个triangle。** A970BF对全部属性调用retain_by_index；A97190–A9723A把mask改成连续新编号，拒绝项为u32::MAX；A97260–A97275再映射剩余indices。此helper全部内建属性枚举分支没有逐一重建，已证的是统一资格调用和索引处理。

若构造混合颜色三角形，只留下其中两个indices，当前函数没有补第三点或重三角化。真实选定资源的三角形颜色资格均一致，故该资产集不会从此例产生混合尾项；这不是全产品输入有效性证明。缺颜色分支182512E走panic_fmt；as_f32x3的E4D984要求raw variant4，类型不符E4D9A9走panic；索引越界也有bounds panic。

## 3. 树冠组法线与中心

在原prim_center存在的canopy分支，C541F5读其f32x3，C54456读Vertex_Position，C545A1读Vertex_Normal。C5463D–C54669将原center的12B直接作为array<u32,3> hash key；C54672推进条目，C545D0–C54603记录该组vertex index并累加normal。这是精确位模式分组，没有距离epsilon，也没有按当前空间邻接识别枝条。

令组G的成员是当前过滤后vertex条目：

```text
S = sum(Vertex_Normal[i], i∈G)
prim_normals[i] = normalize_or_zero(S)
prim_center[i] = sum(Vertex_Position[j], j∈G) / |G|
```

C54969–C549DE对S算sqrt(length²)和倒数，并用浮点位检查拒绝无效归一化；零法线和返回零。C54AF0–C54B1B按组indices广播normal；C54C00–C54C43求位置条目均值，C54C50–C54C65广播；C54CBF和C54D0A实际set_attribute到prim_normals/prim_center。它不要求组恰好4个点，名字Quad不能替代成员数证明；重复渲染vertex条目仍各自计权，不是先按位置去重再求四角中心。

原prim_center缺失会绕开这段重算(C5412B→C542F6)，本轮没有发现默认生成新分组键。不能把任意没有该属性的网格声称已能通过树冠shader必需输入验证。

## 4. appear_pos、age与原资产统计

两分支均检查appear_pos/age是否已存在。缺appear_pos时C54F28–C54F6F和C55249–C5528D创建长度对应的零vec3；缺age时C5504B–C55105和C55369–C55455填1.0。已有则跳过添加。两路还在C54330/C543E3移除名为id的旧mesh属性；不把这个id同实例PlacementData.id混为一物。

本轮重新hash并读三个原JSON的属性计数，没有导出坐标。下列是按已证资格计算的静态候选结果，未实际运行processor：

|源模型|源vertex/index|canopy vertex/index|trunk vertex/index|canopy原center位模式组|
|---|---:|---:|---:|---:|
|branchy_tree_v1|2703/3597|1248/1872|1455/1725|312组，每组4条|
|mid_distance_tree_v1|1740/1740|1740/1740|0/0|290组，每组6条|
|mid_distance_tree_v1_trunk|234/1329|0/0|234/1329|0|

三者已有Vertex_Position/Normal/Color、prim_center、appear_pos、age，没有prim_normals；无越界index、非三项尾indices或mixed资格triangle。branchy源age约[-6.22e−18,1.00749]，mid冠[0,1]、mid干[0,1.00584]。所以CPU这一阶段不应被写成把所有age clamp至[0,1]或按Y重新生成age；原非零appear_pos也被保留，其离线制作工具仍unknown。

## 5. 发布侧已证与断点

90E660 spawn_prefabs在90EC82调用912250 create_prefab_gpu_instances。912292按prefab name从MeshAtlasLibrary.get_by_name获得列表，9123A0/9123B6读8B条目的+0 meshID和+4 subset byte，逐条调用GpuInstance.new，再9123E5调用GpuWorld.create_instances<PlacementDataSsbo,...>，count=1。

GpuInstance.new(947FA0)的9480DA–9480EA将源position前三float、half(scale)和meshID低16位写成16B描述。957070在95780A分配IndexCondenser条目，957882–957886按denseIndex*16复制该描述；957912–957928按**同denseIndex*48**复制完整PlacementData三个16B块。95789A/9578BA以及95794A/95796A用原子比较维护两类记录的待上传min/max索引。

这证明CPU staged payload按同一dense slot对应；动态vtable调用和真实GPU transfer没有追完整，因此不称这里已经执行GPU上传。两个atlas条目会各创建一个实例、拷贝同一源48B参数，但**不能直接将这两条断言为本轮加工出来的canopy/trunk meshID**，atlas注册桥还缺证据。

强弱链：

```text
原JSON属性 → CPU颜色split → canopy分组/属性写回 → processed mesh缓存
processed mesh/PrefabPart …[atlas注册未贯通]… atlas meshID列表
ECS spawn_prefabs → atlas lookup → 每条16B+48B同dense staging
CPU staging …[transfer/descriptor未贯通]… shader实例buffer消费
```

56的树shader字段消费作为下游接口复用，没有再次用相同shader数学替代缺失箭头。

## 6. 贯通构造例

自造六个vertex，indices=[0,1,2,3,4,5]，B=[0,0,0,1,1,1]。canopy保留0/1/2，indices=[0,1,2]；trunk保留3/4/5，旧→新编号为3→0、4→1、5→2，indices同为[0,1,2]。appear_pos/age各条跟随原vertex筛选，不另算生长时间。

给前三点位置(0,0,0)、(2,0,0)、(0,2,0)，原prim_center都为同一个自造键(7,7,7)，normal均(0,0,1)。该组S=(0,0,3)，广播prim_normals=(0,0,1)，重新广播prim_center=(2/3,2/3,0)。原center键只是分组标签，不会继续保留其数值(7,7,7)。若三normal全零，结果normal为0。若原key不同一个float32 bit，即使位置贴近，也不会因距离近自动合组。

同一自造输入若缺appear_pos/age，会补零vec3和1；若已有age=.2/.4/.6，三值保留。没有运行原游戏或使用原资产坐标。

独立发布演算：假定atlas有meshID5与6两条、各subset为2，源position=(10,0,20)、scale=1。分别产生16B描述(position、halfScale=0x3C00、u16 meshID5或6)，两个dense slot各复制相同48B参数。若分配的dense slot为10、11，则参数写址为base+480/base+528，描述写址为base+160/base+176。这是条件演算，不冒称游戏实际分配的ID或atlas内容。

## 7. 交付与未知

native-range-summary.json保存15个范围RVA、file offset、size/SHA、指令数量与listing；native-selected-subranges.json保存细范围字节hash及指令来源；source-attribute-audit.json保存三资源身份和聚合统计；findings.json保存claim/公式/构造例和验证。全部身份/hash复核通过，不等于GPU执行或完整反编译语义验证。

未做：不扩大renderer；未追processed mesh→atlas注册与真实transfer/descriptor，未追所有动态实例修改、dirty范围消费和删除；没有私存档/游戏运行/工具安装或构建。REA仍是既有不可用状态，静态fallback不伪造Evidence/session ID。

风险：将vertex/index资格说成完整triangle裁切、把原center键当最终center、将资源age说成CPU实时生成、将同dense staging说成最终GPU提交，都会夸大当前证据。未见L-system仍只适用于选定资源加工和变形范围，不能推断整个产品或离线工具。
