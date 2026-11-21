# 恒川振动试验室 V1 整卷交换台

这是一个只使用 Python 3.11 标准库和 SQLite 的正常 V1 业务工程。

## 业务流程

1. `station.intake.submit` 登记批号、按帧读数和原件位置。
2. `station.revisions.freeze_input` 固定登记快照并生成连续二阶差分卷。
3. `issue.publish.issue` 按指定修订发行独立清册和完整卷件。
4. `receive.intake.accept` 在独立夜班库中核验并提交实收。
5. `receive.intake.receipt` 按实收号读取固定读数、原位和出处。
6. `review.signoff.report` 按非负整数门槛形成异常摘录和峰值报告。
7. `review.signoff.get_report` 按报告号复领签发时的报告。

V1 的二阶差分从 `(前值=0, 前一阶差分=0)` 起步。读数 `x` 的一阶差分为 `x-前值`，二阶差分为 `一阶差分-前一阶差分`。解码先把二阶差分加入一阶差分，再把更新后的一阶差分加入前值。状态跨空帧和普通帧连续推进。

读数是精确整数。帧可以为空，空帧保留帧位。每个帧必须带有原件标识和原件帧位。同一批内不能重复引用同一个原件帧位。

发行清册固定发行号、修订号、卷首摘要、帧数、逐帧条数、逐帧字节摘要和原件来源。卷件携带原卷首与每个原始帧字节。夜班核验通过后，清册快照、原序读数、原位、原件出处和回执在同一 SQLite 事务中提交。

阈值比较包含等号。峰值来自全部读数。无读数时峰值为 `None`，有读数但没有异常时仍保留峰值。

## 回归与演示

标准回归入口由运行平台提供并从工程根目录执行。

```text
python3 -B check_project.py
```

独立演示使用真实的登记、冻结、发行、离线实收和阈值复核入口。

```text
python3 -B demo.py
```

演示会输出一行 `POINTWISE_SCENARIO` JSON，包含独立手算预期、实际实收和下游报告结果。

## SQLite 使用

`RevisionStore`、`IssuedStore`、`ReceiptLedger` 和 `ReportStore` 的初始化是幂等的。重复初始化只补表，不清除已有业务数据。各库分别保存台架冻结、发行账、夜班实收和复核报告。实收和报告的提交失败都在事务边界内回滚，重开相同数据库后只读到已提交成果。`ReceiptLedger` 在旧库上幂等补出可空的 `readings.correction_id` 列：V1 历史行该列为 `NULL`（领取时读作 `None`），V2 窗内行记录更正号、窗外行同样为 `NULL`；V1 与 V2 回执在同一账本中共存。

## 目录职责

- `station` 负责采集批、原件位置、冻结登记和修订。
- `media` 负责精确整数、帧字节、二阶差分编码、解码和原序定位。
- `issue` 负责清册、卷件、发行记录和按号复领。
- `receive` 负责离线核验、出处、实收事务和回执。
- `review` 负责阈值计算、报告持久化和复测摘录。

V2 窗口替换、原流接缝依据、替换件独立验收和更正出处由下列模块实现，并与 V1 链路并存：`media.stream`、`issue.replacement_manifest`、`issue.replacement_manifest_wire`、`issue.replacement_package`、`receive.replacement_verify`。

## 整帧替换交付契约

在 `issue.publish` 新增 `make_replacement(revision_store, issued_store, revision_id, first_frame, last_frame, readings, correction_id)`，返回 `IssuedRecord`。按 `IssuedStore.get_issue(issue_id)` 可取回该次发行的清册和卷件原字节。发行以传入的冻结修订为准，原修订仍可按 V1 发行。

帧号从零起，`first_frame` 和 `last_frame` 是所选连续窗口的两端，均包含在内，须有 `0 <= first_frame <= last_frame < frame_count`。没有帧的卷没有合法窗口。`readings` 为按窗口帧顺序给出的列表或元组，每帧也是列表或元组，逐帧条数与原帧相同。空帧对应空序列。更正号 `correction_id` 是非空白字符串。读数须为精确整数，布尔值、浮点数和数字字符串无效。可见实收值沿用 SQLite 有符号 64 位整数范围，差分和续解中间量按精确整数处理。

### 两路交付

`IssuedRecord.manifest` 和 `IssuedRecord.package` 均为 UTF-8 JSON 字节。清册以独立可信渠道交付，沿用 V1 清册的字段与原帧条目含义，`version` 填 `2`，增加 `first_frame`、`last_frame`、`correction_id` 及用来核验实际更正内容和续解依据的信息。窗内帧的清册条目仍记录原帧条数、原字节摘要及原出处。

卷件同样带 `version`、`issue_id`、`revision_id`、`first_frame`、`last_frame` 和 `correction_id`。`header` 使用 V1 的 Base64 表示，携带原卷首字节。`frames` 按原帧序每帧恰有一项。保留帧用 `{"frame_index": i, "data": "<原编码字节的 Base64>"}`，更正帧用 `{"frame_index": i, "readings": [更正读数]}`。更正帧的位置与原修订共同标识原帧，原出处由清册提供。窗内原帧编码和原读数序列不随件交付。

续解凭据的表示由实现选择并在此文档说明。本实现的凭据是独立清册 `continuation` 字段：它携带 `revision_id`、窗口两端、逐帧的原流入口/出口状态 `(previous_value, previous_delta)`，以及对该结构的规范化 SHA-256 `digest`。卷件只携带同一个 `continuation_digest`，不携带状态明细；实收时先按独立清册重算 `digest` 确认清册自洽，再核对卷件摘要与之相等，随后从原卷首种子出发，逐帧用清册状态校验保留帧原字节的解码结果：每帧入口状态必须与清册入口相等，保留帧解码后的出口状态必须与清册出口相等。发行时可以全量解码。独立清册必须能核对所用续解依据来自所选原修订和实际窗口边界。若辅助凭据随卷件传送，实收必须凭独立清册核对该凭据。实际保留的原帧须由核验后的原流状态和原编码字节解出。更正值只进入实收正文：窗内帧输出更正值后，原流状态直接跳到清册记录的该帧原出口状态，更正值不参与任何差分推进，因此后缀帧仍按原差分流解释，原流续解状态不变。窗口终止于末帧时没有后缀要恢复。

### 实收与复领

在 `receive.intake` 新增 `receive_replacement(ledger, manifest, package)`，接收上述两份字节，返回 `AcceptedVolume`。两份材料须与同次发行、同一修订和同一更正窗口相符。原卷首、保留帧的字节和条数须与独立清册相符。错版、缺帧、重帧、错窗、更正内容不符或续解依据无效时拒收。格式或配对错误抛出 `ValueError`，发行所指修订不存在沿用 `KeyError`。

读数按原帧及帧内原序输出，`position` 沿用零起 `frame_index`、`reading_index` 和 `ordinal`，`source` 保留原帧出处。V2 每行另可读 `correction_id`，窗外为 `None`，窗内为此次更正号。清册、读数及出处随回执一次提交，`receive.intake.receipt(ledger, receipt_id)` 在重开后返回原实收结果，包括更正出处。核验或实收提交失败不留下本次新增读数或成功回执，故障解除后可重试原件。保持 V1 的字段含义、旧库和历史领取。

### 样例

将下列数据的 `batch_id` 和 `frames` 传给 `submit`，再用登记号执行 `freeze_input`。

```json
{
  "batch_id": "rig-day",
  "frames": [
    {"readings": [1], "source": {"object_id": "rig-A", "frame_index": 20}},
    {"readings": [2], "source": {"object_id": "rig-A", "frame_index": 21}},
    {"readings": [3], "source": {"object_id": "rig-A", "frame_index": 22}},
    {"readings": [4], "source": {"object_id": "rig-A", "frame_index": 23}}
  ]
}
```

以 `first_frame=1`、`last_frame=1`、`readings=[[10]]`、`correction_id="QC-17"` 发行。在夜班库实收应得 `[1, 10, 3, 4]`，全卷序号为 `0, 1, 2, 3`，原帧出处仍为 `rig-A` 的 `20, 21, 22, 23`，仅序号 `1` 有 `QC-17`。帧 `0, 2, 3` 的编码应与原卷逐字节相同。用同批下一修订 `[2, 4, 6, 8]` 重做该窗口，帧 `2, 3` 的原编码与前一修订相同，但它们应解为 `6, 8`。把这两次发行的续解依据交错使用应被拒收。

空帧样例按原序录入 `[[], [1, 2], [], [3, 4]]`，四帧原件可用同一对象的四个不同原帧位。用窗口 `0..2` 和 `[[], [7, -2], []]` 更正后，实收为 `[7, -2, 3, 4]`，前两笔的原帧位为 `1`，后两笔为 `3`，全卷序号连续。空帧没有读数行，仍计入覆盖与帧号。

### 交付核验

现有 `.pointwise-runtime.json` 用于调用核验和演示，从工程根目录运行。让核验入口运行全部原回归及新增的替换件联合核验，业务不符时返回失败。演示使用上述第二帧更正样例，从真实发行取得两份材料，移开源库后实收，再在重开的夜班库按回执号领回，展示实际读数及原位、更正出处。
