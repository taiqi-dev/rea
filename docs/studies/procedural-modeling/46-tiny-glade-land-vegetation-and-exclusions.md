# Tiny Glade 陆地植被：候选、密度、排除与贴地

本轮确认花园和建筑周边灌木/花朵的GPU自动候选、资格与尺寸；草采用确定性候选位置、双通道排除/缩高图；树木找到一条资源预置转换路径。完整活动列表、旧实例清理与局部补种时序仍未知，不能把这些入口合成一套统一植被生成器。

后续[51计数与活跃列表](51-tiny-glade-vegetation-counts-and-active-list-rebuild.md)已补通全局draw模板reset、草ActiveCount clear、逻辑ID到活动前缀及选定LOD0消费；跨系统顺序、最终indexCount补写和逐地块补种仍未知。本篇保留候选/密度公式，清旧的新证据以51为准。

树木资源和干冠展开见后续[56](56-tiny-glade-tree-resources-growth-and-canopy.md)，岩层的单元网格/组合mask位移见[57](57-tiny-glade-rock-mesh-displacement-and-masks.md)；它们没有补写完整森林拓扑生成或逐地块补种。

水生植物见[08](08-tiny-glade-water-vegetation-and-surface.md)，常春藤见[21](21-tiny-glade-ivy-roots-and-state.md)，跨模块更新见[45](45-tiny-glade-shared-invalidation-and-rebuild.md)，身份与复核见[47](47-tiny-glade-four-systems-evidence-ledger.md)。下面是发行版CPU绑定和SPIR-V消费的静态推导，未执行shader。

## 1. CPU确实选择了不同的自动生成管线

`9AE210 garden_spawn_vegetation` 获取BushSsbo/FlowerSsbo，实际查找字符串 `country_core/garden/spawn_bushes_garden:main` 并绑定/调度；灌木逻辑范围90×90。`B32850 spawn_vegetation_around_buildings` 实际选建筑周边的bush/flower变体，逻辑范围分别90×90、150×150，与花园输出使用对应typed buffers。

这比文件名候选更强，但全部纹理descriptor身份、过滤/wrap方式、尾部工作组的有效范围和调度频率仍未恢复。shader没有在所查候选处统一检查invocation<逻辑维度，不能直接把90×90当实际输出数。

## 2. 公共数学：整数hash、平滑阈值和值噪声

下面记H为已恢复u32整数混合，所有整数操作按mod2^32：

```text
n+=n<<10; n^=n>>6; n+=n<<3;
n^=n>>11; n+=n<<15;
U(H)=bitcast_f32((H&0x7fffff)|0x3f800000)-1
```

U属于[0,1)。记S(a,b,x)为实际GLSL SmoothStep：有限a<b时，t=clamp((x−a)/(b−a),0,1)，S=t²(3−2t)。另一个尺寸pulse为：

```text
Pulse(c,w,v):
abs(v-c)>w → 0
否则 t=abs(v-c)/w，返回1-t²*(3-2t)
```

V(p)是四格随机值经平滑双线性插值：b=floor(p)、f=fract(p)、权重f²(3−2f)。格点Q的选定指令为：

```text
q=(x*1664525+H(y)+1013904223)*1664525  // u32 wrap
q^=q>>11
q^=(q<<7)&2636928640
q^=(q<<15)&4022730752
q^=q>>18
```

格点有符号坐标以i32位模式转u32，随后用U(q)形成值。四格插值是实际恢复的表达式，不将其只凭名字称为梯度噪声。

### 构造例：四格插值

给四格值(.2,.8,.4,1)，局部f=(.5,.5)，平滑权重仍为(.5,.5)，V=.6。移动p会连续改变权重；改变资格图并不一定改这个候选噪声。

## 3. 花园灌木：格点偏移、排除和尺寸

选定灌木候选，invocation为(x,y)、逻辑维度D：

```text
r=U(H(x*y+x))
p=130*((vec2(x,y)+.5)/D-.5)+vec2(-1+2*r)
```

两个方向使用同一个r，因此这项jitter沿对角线偏移。资格读取的选定通道为：

```text
path.R<=.2
不是(rocky.R>0 且 slope>.9)
water.G<=.3
foliage.R<=0
building_nonblur.R<=.5
g=garden.G+.005>.5
```

slope来自四个高度gather：d=(h2+h1−h3−h0,h0+h1−h3−h2)，再算 `length(.5*26.5*d/(130/heightmapDims))`。没有从变量名猜成地形三角形法线。

通过后用花园g控制尺寸：

```text
a=clamp(S(.45,1,g)+.2*S(.6,1,g),0,1)
rS=lerp(.8,1.2,U(H(x+y)))
z=lerp(.3,.8,sqrt(a))
sx=sz=min(rS*z,.75)
sy=min(rS*rS*z,1.2)
Y=lerp(-2.5,24,terrain.R)
```

输出对drawcommand[9].instanceCount原子递增，旧计数作为48B BushXform索引。另一个条件花分支用计数[10]和64B FlowerXform；它发生在已通过灌木资格之后，不能当成独立全域花采样。

### 构造例：候选通过，再被水域排除

x=y=0、D=(90,90)，H(0)=0，p≈(−65.27778,−65.27778)。此格在域边，真实采样还依赖边界配置，所以资格例另给path=0、rock.R=0、water.G=0、foliage=0、building_nonblur=0、garden.G=.8、terrain.R=.2。

g=.805通过，贴地Y=2.8；a约.816、z约.752、rS=.8，sx约.601、sy约.481。只将water.G改成.31就不通过，不递增灌木计数。这是样本输入演算，不是运行输出。

## 4. 建筑周边灌木：两个建筑通道控制不同用途

共同道路/坡度/水域/foliage排除与上段对应。建筑变体还排除plant_sample uint4任一分量非零、garden.G>.3、未模糊building.R>.99999。

额外资格为模糊building.R>0、V(p)>.5，以及size_test≥.3。尺寸主量却由building.G控制：

```text
A=Pulse(.4,.3,building.G)
z=lerp(.2,1,sqrt(A))
dims=.75*(min(rS*z,.75),min(rS*rS*z,1.2),min(rS*z,.75))
size_test=.75*min(rS*lerp(.2,1,sqrt(Pulse(.4,.3,building.R))),.75)
```

Y同样取terrain解码高度；theme_id=4的选定分支再减.5。某些已生成bush另经hash门槛输出花。建筑图R/G通道全部上游生产语义尚未恢复，不把pulse的数值直接命名为世界距离。

### 构造例：沿建筑相关区域的密度筛选

给共同排除均通过、plant_sample=0、garden=0、nonblur building.R=0，模糊building.R=G=.4、V=.7、rS=1、terrain=.2、theme≠4。两个pulse=1，size_test=.5625通过；dims=(.5625,.75,.5625)，Y=2.8。将V改成.5，严格>.5失败。

这条变体由建筑相关图筛选候选，不表示把建筑内部均匀填满灌木。

## 5. 花朵：两套候选和不同密度门槛

每invocation的花管线有两个候选。第一个用 `r=U(H(x*y+x+100))`，在base上加两个方向相同的±.75偏移。第二候选用另一seed链：

- 花园：`OpConvertFToU(100*r-34)` 后送H。
- 建筑周边：`OpConvertFToU(100*r-341)` 后送H。

第一表达式可负，第二在r∈[0,1)时始终负。本轮只确认这个转换指令，未核目标设备行为；不能自行补成wrap、饱和或某个固定返回值。因此第二候选的跨设备精确seed结果仍未知，不据此宣称游戏异常。

花园两分支分别使用 `2*V(.5*p)>.6` 和 `2*V(.5*p+100)>.6`，并要求garden.G>.425；建筑两分支使用V>.6，没有乘2，还需building.R>0和sx≥.4。两者的共同排除/非模糊建筑资格也有区别。

花园尺寸：

```text
a0=Pulse(.6,.2,g)+1.5*S(.9,1,g)
a1=Pulse(.65000003576,.3,g)+1.5*S(.9,1,g)
m=lerp(.5,1,a) // a此处未clamp
dims=1.5*(min(rS*m,.75),1.2*rS*rS*m,min(rS*m,.75))
```

g使用原garden.G，没有bush的+.005。基准Y为.5，高garden平滑项>0时用1.1；最终仿射位置XZ另采terrain，将地面高度加到translationY。建筑花以building.G的pulse控制m=lerp(.2,1,a)，中心为.55000001192、两个宽度参数为.3/.4，输出尺寸没有花园外乘1.5。64B FlowerXform两分支tag=0/1，原用户可见品种枚举未恢复。

### 构造例：相同噪声，两种管线资格不同

共同排除通过，花园分支0 g=.6、V=.4、rS=1、terrain=.2：2*.4>.6成立，a=1，dims=(1.125,1.8,1.125)，基准Y=.5时translationY=3.3。

同样V=.4在建筑花分支不满足>.6。改为V=.7、building.R>0、building.G=.55，a=1，dims=(.75,1.2,.75)，sx≥.4通过。本例只使用第一候选，不演算未确认的负值无符号转换。

## 6. 草位置来自确定性bit反转序列

`cull_and_bucket_grass2_lod0` 的所选路径读取active ID i：

```text
i<57344:
  n=i%14336+1; N=14336; W=130
否则:
  n=(i-57344)%30720+1; N=30720; W=190
p=W*((n/N,reverse_bits32(n)/2^32)-.5)
```

reverse_bits由16位旋转及1/2/4/8位交换指令实现。这证明该路径的位置可由ID重算，不是每次编辑都独立抽一套随机点。

多个ID可能经过mod得到相同n；i范围、层级和其他资格未完整恢复，因此N不是最终可见草数，也不把57344解释成全场景草预算。主地形分支用Y=−2.5+26.5*terrain.R，背景分支还有独立bounds/高度来源。

### 构造例：第一候选的位置

i=0，n=1，reverse_bits32(1)=2^31，p≈(−64.99093,0)。若主terrain.R=.2，Y=2.8。还需要frustum、层级和removal资格，不能称已产生可见草。

## 7. 草排除和缩高使用两个通道

`combine_grass_removal` 实际读取water_mask.G为W，进入下式前不变换。令p=S(.1,.2,path.R)，b为3×3邻域未模糊建筑R的max，j为3×3邻域garden.G>.402的指示值max：

```text
R=max(
  I[p>.9], I[foliage.R>0], S(.12,.28,min(W,1-W)),
  I[rock.R+S(0,.5,rock.G)+.4*rock.B>.2], j)
q=max(1-S(.3,.4,b),.4*S(.5,.7,b))
G=clamp(min(1-.7*p,q,clamp(1-.5*W,0,1)),0,1)
```

岸带项在W=.5附近高，在W=0/1时低，不能概括为所有水下草一律删除。G另有water缩高。b不同区间也可令q降到零或回到.4，不宜把建筑项简化成单个线性距离衰减。

草顶点路径比较确定性fraction噪声n<R，命中时跳过当前路径；G乘局部Y缩高。整体compute culler则在五个采样点R的minimum≥1时跳过候选。片段/顶点资格和整体剔除不是同一层。

### 构造例：先缩高，再形成排除

path.R=.15、W=0、foliage=0、rock=0，garden/建筑3×3全零：p=.5，R=0、q=1、G=.65。草局部Y缩为.65倍。

任一garden邻样改成.403，会令该mask样点R=1；顶点fraction n<1时通过排除比较。整个候选还需culler的五点条件，不由单个样点推出。建筑b=.45时q=0；b=.7时q=.4，这是原式的不同区间结果。

## 8. 树木目前确认资源预置转换

`A32F00 spawn_preplaced_trees` 的选定入口关联trees.json字面量，`A33142` 反序列化Vec<PlacementConfigEntry>，以80B配置步长遍历；`A33553` 解析PlacementDataSsbo，`A336B5` 插入ConvertedPreplacedTree标记。

这确认一种资源预置树转换职责，没有证明全部树预置，也未恢复玩家树、自动森林及远景树的全部生成算法。不能把“加载配置后有树实体”写成已恢复树密度采样。

构造例：提供一个有效配置项和有效PlacementData，选定转换路径写入marker。没有执行真实资源加载，也不演算未恢复的森林密度。

## 9. 更新、读回与补种的范围边界

`9AE7C0 garden_rasterize_from_cpu` 在 `9AEA47` 检查已取得资源+29B，非零时 `9AEA59` 清该字节并进入上传/blur路径；不能仅因+29B接近WorldRaster+29A就称为同一状态。

PlantSampleRaster另有自己的 `A85430 copy_to_staging`，在 `A858B0→9C5460` 发布DirtyTiles；`9EB010`读取对应staging并绑定upload_plant_sample。它与WorldRaster的泛型发布路径分别记录。

`B325D0` 实际绑定read_bush_positions_for_cpu：shader用48B affine作用于原点并把XZ写入CPU候选buffer。元素0的两个float槽重复存整数count的位模式（bitcast），不能按数值float(count)读取；后续元素从bush[i−1]读取。完整CPU读者、读回完成时机和实例重用尚未贯通。

### 构造例：脏标志不是补种完成

资源+29B初始1，本次进入上传/blur并清零；下次仍为0就跳过这个dirty分支。这个过程不证明自动spawn立即执行、计数已经reset，或只补种该tile。候选ID可重复计算、排除图变化和旧输出清理分别需要自己的证据。

## 10. 独立实现与未确认项

可独立采用确定性候选、空间值噪声密度、多个资格图及双通道缩高/排除。将花园与建筑周边规则分开，有利于控制交界区域；把输出计数、逻辑ID和bufferslot分别管理，才能清楚解释编辑后的保留与替换。

未做：未运行植被生成或测量视觉密度，未恢复全部纹理生产/采样边界、草活动列表和远层级、所有实例计数reset/清旧及森林系统。

风险：负浮点转无符号整数的设备语义未知；逻辑调度尺寸不等于实例数；当前已恢复候选与资格，完整局部补种生命周期仍部分回答。
