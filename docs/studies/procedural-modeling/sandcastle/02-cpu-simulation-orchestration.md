# CPU 如何驱动沙水模拟

## 从帧到海滩

**观察**：`Game.Run` (`0x18048D110`) 先调用 `0x18048DEA0` 处理全局状态，再把当前 step 与 `dt` 交给 `Beach.Run` (`0x180428010`)，返回后递增 step。`Game.FixedUpdate` (`0x18048A930`) 则先检查 phase，再取时间并进入同一 `Beach.Run`；这提供了定时更新的证据，但目前没有运行时帧率记录。`Beach.Run` 按对象字段顺序触发 Ground (`+0x20`)、Water (`+0x28`)、Air (`+0x30`)、Dirt (`+0x48`)、Gravel (`+0x50`)、Plants (`+0x58`)、Readback (`+0x40`)、GI (`+0x38`) 的对应运行入口。这里 `+0xNN` 是当前 native 对象布局偏移，不是序列化文件偏移。[方法映射](01-artifact-and-method-map.md)和 `disasm/Game_Run_3cd.txt`、`Beach_Run_full.txt` 可复查调用地址。

把上述观察整理为自有伪代码：

```text
tick(step, dt):
    update_global_simulation_state(dt)
    beach.ground.run(step, dt)
    beach.water.run(step, dt)
    beach.air.run(step, dt)
    beach.particles.run(step, dt)
    beach.readback.run(step, dt)
    beach.lighting.run(step, dt)
    step += 1
```

它说明**调度关系**，不表示这些层全部同步完成或在 CPU 计算数值方程；GPU dispatch、异步读回和渲染的精确时序仍取决于 Unity API 与资源状态。

## 地面与水的计算步骤

`Ground` 元数据字段包括 `resolution`、`cellsCount`、`cellSize`、`scaleBias`（来自 `Layer`），以及 `gravityForce`、`noiseFactor`、`colliderResolution`、`kernelVelocityIntegration`、`kernelHeightIntegration`、`kernelUpdateTangent`、`kernelUpdateObstacleHeight` 等。`Ground.Setup` (`0x180450740`) 取得网格维度、配置内核与输入缓冲，并调用 `PlaneGenerator.Generate` (`0x180493DB0`) 建立四个 `planeChunks`；`Ground.Run` (`0x18044FF60`) 向计算缓冲写每步参数，依次通过虚调用触发两个主要积分 kernel。它用 `Compute.Step` (`0x180474E30`) 循环推进，然后在相应 step 上轮换调用一个 `PlaneChunk.UpdateMeshCollider` (`0x18045F120`)。本地着色器中的通量与侵蚀具体算法见 [GPU 研究](04-gpu-simulation-and-brush.md)。

`Water` 也继承 `Layer`，额外具有 `evaporationFactor`、`floorBlurIterations`、`level`、`enableSpawn`、`enableEvaporation`、`spawnRate`，以及 floor、velocity、height、advection、amount 等 kernel 字段。`Water.Run` (`0x1804832D0`) 配置参数并做多次 kernel dispatch；在状态许可的分支会调用 `Water.Spawn` (`0x180485130`) 与 `Water.SpawnDirt` (`0x180484AE0`)。`Ground.Run` 与 `Water.Run` 都调用 `Compute.Step`，而 `Compute.Step` 保存剩余时间/步数，通过阈值决定本轮是否继续，并具有 `0x3E8`（1000）次的安全上限比较 (`0x180474EDA`)。这支持“有界子步进”而不是“每 Unity 帧只算一次”。`Water.Run` 的实际每帧子步数、出生量和蒸发量取决于序列化参数及当前状态，单从调用名无法断言。

**构造算例**：若某一帧 `Beach.Run(step=42, dt=Δt)`，CPU 先让 Ground 的子步控制器判断是否需要 0、1 或多次沙核更新，然后 Water 用自己的参数和控制器决定水核更新；后续 Readback 可为工具、碰撞与视觉消费提供采样。帧结束后 step 变为 43。此算例只演示调用/状态关系，未把未确认的时间步长或网格分辨率填成数字。

## 读回与边界

`ReadbackCell` 的元数据字段包含 `waterVelocity`、`groundTangent`、`waterAmount`、`sandAmount`、`groundHeight`、`crestSpawn`；`Readback.UpdateCellsImmediate` (`0x1804654B0`) 可触发当前 buffer 的即时读取。`Shovel.OnAction` 等工具读取海滩命中与容量状态，说明 GPU 网格结果至少部分反馈到交互 CPU。字段名仅表明可表达的信息；哪个字段的取值来自哪一个 GPU 纹理/缓冲，需结合 [Readback shader 证据](04-gpu-simulation-and-brush.md) 才能确定。此研究没有运行时读取数值，也未证实不同海滩具体 `resolution` 默认值。
