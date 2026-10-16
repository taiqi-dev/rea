# 四款游戏：原生等待、恢复刷新、调度屏障与订阅可达性

接续[102](102-four-static-lifecycles-seed-producers-and-listeners.md)。本轮继续四条指定静态链：**沙堡进入UnityPlayer请求／回调／等待函数，掘地求财把恢复范围接到mesh和碰撞接受门，Tiny Glade分清消息直接写入与deferred命令，SUMMERHOUSE补查列表写端与真实启停条件。**运行验证全部 **Not Run**。

| 专题                                                                                                         | 新证据与结论                                                                                                                                                                               | 尚未闭合                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| [沙堡22：native旧请求等待与取消](sandcastle/22-native-readback-wait-cancel-boundary.md)                      | 3996项名称／函数指针平行表，五个接口由函数体交叉核对；请求节点有指针／世代和回调／释放槽。WaitOne／WaitAll在状态1时经虚槽+8C0等待；Clear直接进入buffer回收。                               | 表注册消费者未接通；回收虚调用+2E0与等待虚槽实际类型、间接取消／等待及回调线程仍未知。不能断言Release会取消，也不能断言旧回调必到新数组。 |
| [掘地求财20：部分恢复后的LOD／mesh／碰撞](digging-a-hole/20-partial-restore-lod-mesh-collision.md)           | **变化盒修正为旧树终端盒＋匹配提取的新chunk叶盒**；placeable不直接追加本次数组。默认LOD选当前render chunk，renderer有static／空key／任务槽门；完成mesh与Chaos cook分别检查当前令牌／编号。 | 默认动态类型、placeable独立通知、实际render tree／在飞任务分布和时延未观察。调用UpdateBounds不等于mesh／物理完成。                        |
| [Tiny Glade103：快照后运行门与deferred](103-tiny-glade-snapshot-run-conditions-and-deferred.md)              | 快照调用属于load_game条件分支；Public和普通砖各有run_without_applying_deferred／run_unsafe包装与参数获取门。Public直接追加16 B消息；砖由双缓冲游标取未读消息。                             | 具体in_set／run_if、executor ApplyDeferred与消息轮换节点尚未定位。参数门不是外部run_if，阶段标签不证明具体系统同帧次序。                  |
| [SUMMERHOUSE21：列表写端与重复订阅](summerhouse/21-listener-writers-and-repeat-subscription-reachability.md) | 主程序集1006/1006方法扫描，列表仅四个直接用户；没有额外正常清表。14件粒子stopAction=None，22个祖先没有动画／UI启停组件；debug切换目标是三个UI对象。同环境已加载分支跳过加载。              | 剩余SetActive目标、动态调用、共享变量跨场景身份和同一listener真实启用循环仍Partial。场景销毁后的旧引用残留与同实例重复Add分开。           |

## 对已有解释的收紧

掘地求财[19](digging-a-hole/19-post-clear-failures-and-rollback-boundary.md)关于变化盒来源的简述不完整，新块在ExtractChunk之后确有写端。旧树终端盒通常覆盖整个旧根区域，所以“有变化盒通知”也不等于只刷新旧挖掘点或最小局部；实际成本取决于当前render octree相交key及任务门。失败bool／无回滚结论不因此改变。

Tiny Glade的 `OnWallChanged` 可见性不能用 `Commands` flush 一句话解释。资源中的候选写入、消息队列追加、读游标、实体命令应用和最终GPU完成分别有自己的条件。沙堡的native世代只约束请求节点身份，尚没有连接到游戏Readback重建世代；SUMMERHOUSE的资源pathID也不能当作跨场景托管实例身份。四者都需要保留“对象是谁”和“当前结果能否提交”的区别。

## 验证与交付边界

新普通raw在ignored `.cache/procedural-modeling/static-scheduler-followup/`，正文保留当前制品路径／长度、PDB或MVID身份、地址／token、解析范围与条件演算。沿用四个精确目标本次调查的摘要授权，未重算摘要；没有读取私人存档、运行游戏／Unity、附加进程、执行目标函数或GPU、安装软件、操作鼠标／前台。旧Ghidra超时条件未变、未重试；这些普通输出不是REA Evidence。

新增长期只读工具位于正式专题tools目录。检查包括：当前字节／表槽／CIL锚点，完整资源复读，输出覆盖拒绝与错误profile，文档UTF-8／链接／围栏／语法，以及仓库文档检查。具体结果见本轮raw的`focused-validation.json`、`document-validation.json`和仓库／交付回执。没有FPS、延迟、显存或内存实测，也不由静态链宣称某个玩家故障已经发生。

后续静态题目的顺序、停止条件和新方向单列于[105：下一轮建议](105-next-static-study-recommendations.md)。
