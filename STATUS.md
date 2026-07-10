# 当前状态

## 2026-07-10 对账单持久化增量
- `trades.py` 新增本机私有解析缓存：上传后只保存交易记录 JSON，不保存原始 Excel；下一次有效上传会替换旧缓存，空/无法识别的文件不会覆盖旧数据。
- `app.py` 对账单入口改为“显示个人交易记录 + 更新电子对账单（可选）”；切换标的和重启 Streamlit 后继续读取同一缓存，并在侧栏显示已保存标的数量。
- `.gitignore` 新增 `private_data/`，避免私人交易记录进入版本库。
- `.venv\\Scripts\\python.exe -m unittest discover -s tests -v`：40 项全部通过；`py_compile app.py trades.py` 与 `git diff --check` 通过。
- 本地页面检查通过：持久化说明、更新入口和“从诞生至今”图表选项均正常渲染；未上传真实私人文件进行浏览器测试。

- 最后更新：2026-07-10
- 当前目标：完成“可信决策内核”重构：核心 ETF 的三段战役、可信 RVOL、精简主页面、复盘日志与完整战役回测。
- 当前执行者：Codex（即将交接 Luna）

## Luna 接手说明（2026-07-10）

- 当前分支：`codex/credible-decision-core`；工作区原本就有大量达达未提交的改动，**不可 reset、checkout 或覆盖**。
- 已新增 `instruments.py`：四只核心 ETF 固定为 563360/510300=40/35、518880=35/30、588000=30/25；右侧确认统一为 RSI≥40 且 MACD HIST 较前日改善。恒生、港股、DBO 为实验观察区，不得展示战役或回测结论。
- 已改造 `data.py`：缓存附带来源和 `amount_verified` 元数据；腾讯估算成交额、实验区来源和旧缓存均不允许用于正式 RVOL。
- 已新增完整战役模拟与回测：第一观察位 → 第二观察位 → 右侧确认，三段等权成本；未完成战役不计入收益统计。
- 已重写 `app.py`：侧栏分为“状态与图表 / 复盘日志 / 策略回测 / 策略规则”；主页面只保留状态、四项数字、三条观察和图表；对账单改为本机持久缓存，上传新文件时替换解析记录。
- 已修复 `journal.py`：真实峰值到谷值最大回撤；事后回顾幂等替换，不重复追加。
- 已更新 `trades.py`：新增内存解析 `parse_statement()`，不再让页面读取根目录固定对账单。
- 已更新 `.gitignore`：忽略 `journal/`、`yfinance.cache`、`普通账户电子对账单.xlsx`；**不要删除现有个人文件**。
- 已更新 `requirements.txt`（补充 `yfinance`、`openpyxl`）、`PROJECT_CONTEXT.md`、`PRD.md`；仍需在完成所有最终验证后补充本 STATUS 的“最近验证”。

### 已验证

- `python -m py_compile app.py data.py dashboard.py backtest.py journal.py trades.py instruments.py` 通过。
- `python -m unittest discover -s tests -v`：35 项通过。
- `.venv\Scripts\python.exe main.py --no-plot`：四只核心 ETF 均通过；CLI 输出“战役观察”，不再输出旧“买入条件检查”。
- `git diff --check`：通过；未发现空白错误。
- CLI 已断开遗留 `validate_text.py` 一致性校验调用；`build_buy_checklist()` 与其测试暂保留，等待后续用新战役观察测试替代后再退役。
- 2026-07-10：主页面图表区间新增“从诞生至今”，以当前数据第一天为起点；本地 Streamlit 选项切换验证通过，无浏览器 error。
- 2026-07-10：新增图表区间测试后，全量测试为 37 项通过。
- 2026-07-10：重新运行四只核心 ETF 的完整战役回测，均能输出 20/60/120/250 日统计；563360 完整战役 5 次、510300 58 次、518880 24 次、588000 9 次（仅作当前缓存验证，不代表未来收益）。
- 2026-07-10：`main.py --symbol 563360 --no-plot` 再次确认输出战役观察，无“买入条件”或“一致性检查”旧区块。
- 本地 Streamlit `http://127.0.0.1:8502`：主页面、复盘日志和策略回测导航均已浏览器验证，未发现控制台 error。

### Luna 下一步

1. 重跑全量测试与语法检查（STATUS 写入后尚未重跑），检查 `git diff`，特别确认未误包含个人对账单或日志。
2. 在确认新战役观察覆盖全部使用场景后，再退役旧 `build_buy_checklist()` / `validate_text.py` 测试与旧文案，禁止批量删除。
3. 继续完善完整战役回测的统计展示与复盘页面体验；所有新行为先写失败测试。
4. 最后更新本文件的验证记录与长期事实；不要提交或推送，除非达达另行要求。

## 已完成

- `data.py` — akshare 数据获取 + 本地 CSV 缓存（超过 1 天自动刷新）
- `dashboard.py` — 状态化看盘分析：当前状态 + 一句话解释 + 四步看盘 + 操作理解 + 下一步观察
- `chart.py` — 四层图表：价格（K线 + MA5/10/20 + 布林带）+ RVOL + MACD + RSI
- `main.py` — CLI 主入口，支持 --symbol/--days/--no-plot/--force-refresh
- `app.py` — Streamlit 图形面板，显示状态化看盘解释和买入信号质量回测
- `backtest.py` — 按“距上次有效信号 > 30 天”去重，统计买入后 20/60/120/250 个交易日收益
- 已移除工具内卖出策略、止盈策略回测和持仓卖出参数
- RSI 阈值：563360/510300 使用 35，518880 使用 30，588000 使用 25
- MACD/RVOL 只作为观察辅助，不进入买入阈值和回测规则
- MACD 文案统一为 DIF / DEA / HIST，动能按 HIST 与前一日 HIST 比较
- 看盘解释 `market_analysis` 与 RSI 低位现金池计划 `rsi_cash_plan` 已拆分
- RVOL 固定使用成交额 / 20日成交额均线，缺少成交额时暂不可用，不回退成交量
- `缩量偏强` 文案强调趋势偏强、MACD偏多、RSI正常但 RVOL 偏低，持有观察、不追涨，等待放量突破或缩量回踩
- 终端端到端测试通过

## 使用方式

```powershell
.venv\Scripts\python.exe main.py                  # 默认 90 天窗口
.venv\Scripts\python.exe main.py --days 180       # 半年窗口
.venv\Scripts\python.exe main.py --no-plot        # 只看面板不画图
.venv\Scripts\python.exe main.py --force-refresh  # 强制刷新数据
.venv\Scripts\python.exe main.py --symbol 518880 --no-plot  # 黄金ETF，RSI<30阈值
.venv\Scripts\python.exe main.py --symbol 588000 --no-plot  # 科创50ETF，RSI<25阈值
```

## 下一步

- 用户实际使用反馈
- 面板信息密度可根据实际看盘体验调整
- 如需查看图形界面，优先运行：`powershell -ExecutionPolicy Bypass -File .\start_app.ps1`

## 本轮禁止

- 不输出自动买卖信号
- 不输出卖出策略
- 不引入 ML/DL
- 不实现自动化下单
- 不批量删除文件

## 最近验证

- 2026-06-28：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-06-28：`.venv\Scripts\python.exe main.py --no-plot` 通过，终端显示 MACD
- 2026-06-28：`.venv\Scripts\python.exe main.py --symbol 518880 --no-plot` 通过，黄金 ETF 使用 RSI<30 阈值
- 2026-06-28：`backtest.run_backtest()` 验证 30 天去重后可输出买入信号质量统计
- 2026-06-28：科创50 ETF (`588000`) 阈值从 RSI<30 调整为 RSI<25
- 2026-06-30：按价格位置、RVOL、MACD、RSI 顺序重构 CLI/Streamlit 看盘提示和图表顺序
- 2026-06-30：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-06-30：`.venv\Scripts\python.exe main.py --no-plot` 和 `--symbol 588000 --no-plot` 通过；akshare 刷新失败时已回退到本地缓存
- 2026-06-30：`.venv\Scripts\python.exe main.py --days 180` 生成四层图表，人工查看 PNG 正常
- 2026-06-30：四个 ETF 构图均为 4 个子图；Streamlit 本地页面 `http://127.0.0.1:8501` 返回 200
- 2026-06-30：东方财富日 K 接口断连时自动切换到新浪备用源；四个 ETF 已强制刷新到 2026-06-30
- 2026-06-30：新增 `build_market_analysis()`，CLI 和 Streamlit 共用当前状态、一句话解释、看盘顺序、操作理解、下一步观察
- 2026-06-30：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-06-30：`.venv\Scripts\python.exe main.py --no-plot` 通过，输出状态“缩量偏强”，MACD 显示为 DIF/DEA/HIST，RVOL 进入结论
- 2026-06-30：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过，科创50 RSI 阈值仍为 25
- 2026-06-30：`.venv\Scripts\python.exe main.py --days 180` 通过，生成四层图表 `output\chart_2026-06-30.png`
- 2026-06-30：Streamlit 后台启动，`http://127.0.0.1:8501` 返回 200；四个 ETF 的数据和状态分析函数均跑通
- 2026-07-01：调整 `缩量偏强` 的一句话解释、RVOL 解释和操作理解；MACD 正柱未放大状态改为“红柱为正”
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --no-plot` 通过，`563360` 仍为“缩量偏强”，输出“不适合直接追涨”和 `RVOL > 1.2` 确认线
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过，科创50 RSI 阈值仍为 25
- 2026-07-01：构造 `hist > 0` 且 `hist_today < hist_yesterday` 场景，MACD 输出“红柱为正”而非“红柱放大”
- 2026-07-01：Streamlit 页面 `http://127.0.0.1:8501` 返回 200
- 2026-07-01：重构规则层，拆分 `market_analysis` 和 `build_rsi_cash_plan()`；`market_analysis` 不再默认围绕 RSI 低位现金池逻辑输出
- 2026-07-01：RVOL 改为优先 `amount / amount_ma20`，无 `amount` 时回退 `volume / vol_ma20`（已被后续规则替换）
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --no-plot` 通过，563360 输出 `缩量偏强`，下一步观察符合 RVOL > 1.2、MA5/MA10 缩量回踩、RSI 正常偏强三条
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过，588000 输出 `高位过热`
- 2026-07-01：`.venv\Scripts\python.exe main.py --force-refresh --no-plot` 通过；当前缓存无 `amount` 时显示 `成交量RVOL`（已被后续规则替换）
- 2026-07-01：构造含 `amount` 数据验证 `compute_indicators()` 输出 `成交额RVOL`；构造 RSI 低位验证现金池计划只在 RSI 低位时输出
- 2026-07-01：Streamlit 页面 `http://127.0.0.1:8501` 返回 200
- 2026-07-01：精确调整 `缩量偏强` 的一句话、新买入、加仓、风险警戒文案，保留 MACD 判断逻辑不变
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --no-plot` 通过，`缩量偏强` 一句话和操作理解已按 MA5 / MA10、RVOL > 1.2 文案输出
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过
- 2026-07-01：MACD 边界验证通过：`hist_today <= hist_yesterday` 时输出“红柱为正”，`hist_today > hist_yesterday` 时输出“红柱放大”
- 2026-07-01：Streamlit 页面 `http://127.0.0.1:8501` 返回 200
- 2026-07-01：新增 `start_app.ps1`，启动前会停止本项目旧 Streamlit 进程，降低旧模块缓存导致 ImportError 的概率
- 2026-07-01：Streamlit 页面新增数据日期、数据来源、RVOL 口径和缓存更新时间概览；无 `amount` 时明确提示回退为成交量RVOL（已被后续规则替换）
- 2026-07-01：新增 `tests/test_market_analysis.py`，覆盖成交额RVOL优先、成交量fallback、缩量偏强样本、RSI现金池触发边界、MACD红柱放大边界、高位过热优先级（已被后续规则调整为无成交额时 RVOL 暂不可用）
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，6 个规则层测试全部通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --no-plot` 通过，563360 仍输出“缩量偏强”
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过，588000 仍输出“高位过热”
- 2026-07-01：`powershell -ExecutionPolicy Bypass -File .\start_app.ps1 -NoStart` 通过；`http://127.0.0.1:8501` 返回 200
- 2026-07-01：RVOL 固定改为 `amount / amount_ma20`，无 `amount` 时不再回退成交量，页面和 CLI 显示”RVOL 暂不可用”
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，6 个规则层测试全部通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --no-plot` 通过；新浪备用源含成交额，RVOL 0.80 正常输出
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --force-refresh --no-plot` 通过；科创50 RVOL 1.08 正常输出
- 2026-07-01：重构规则层八项修正：①放量破位警戒优先于短线放量转弱 ②新增弱势下行/趋势偏弱状态 ③高位过热细分为严重过热/高位放量过热/偏热强势 ④强势放量突破仅突破前高时用，否则叫强势放量 ⑤健康回踩增加is_pullback条件 ⑥RVOL增加成交量fallback ⑦清理低吸残留文案 ⑧侧边栏策略规则改名为RSI现金池纪律（独立模块）
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，7 个规则层测试全部通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --force-refresh --no-plot` 通过，563360 缩量偏强、RVOL 口径显示为"成交额RVOL"
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --force-refresh --no-plot` 通过，588000 正确分类为"高位放量过热"（RSI 71 + RVOL 1.39）
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 518880 --force-refresh --no-plot` 通过，黄金正确命中"弱势下行"（之前会掉入中性观察）
- 2026-07-02：新增 `build_buy_checklist()` 买入条件检查模块（RSI低位/MACD改善/无量恐慌/站上MA20），CLI和Streamlit均接入；仅RSI进入低位观察区时才显示，四项条件作为整体发挥作用
- 2026-07-01：Streamlit 顶部去掉大号 RSI/RVOL 口径指标，只保留小号数据日期、来源和缓存更新时间；当前状态仍作为主视觉
- 2026-07-01：本地缓存缺少 `amount` 时会尝试刷新升级；若东方财富不可用且新浪备用无 `amount`，RVOL 暂不参与状态判断
- 2026-07-01：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-01：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，6 个规则层测试全部通过
- 2026-07-01：`.venv\Scripts\python.exe main.py --no-plot` 通过；当前东方财富失败、使用新浪备用，成交额缺失时显示 `RVOL 暂不可用`
- 2026-07-01：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过；高位过热状态不依赖 RVOL，仍可输出
- 2026-07-01：`powershell -ExecutionPolicy Bypass -File .\start_app.ps1` 通过；`http://127.0.0.1:8501` 返回 200
- 2026-07-01：确认东方财富 `fund_etf_hist_em` 当前请求被远端断开，工具自动切到新浪备用源；新浪备用源只有成交量，没有成交额
- 2026-07-01：修复数据缓存策略：若已有缓存含 `amount`，而刷新源缺少成交额，则保留本地成交额缓存，不再被备用源降级覆盖
- 2026-07-01：`fetch_klines_sina()` 新增 `amount` 字段（新浪接口实际已返回成交额，之前被 `cols` 过滤掉）；重构 `load_data()` 为三层数据源：东方财富 → 新浪 → 腾讯，均含成交额；新增 `fetch_klines_tencent()` 腾讯备用源
- 2026-07-02：`build_buy_checklist()` 重构为三场景自动检测（RSI低位买入 / 健康回踩买入 / 放量突破买入），无场景匹配时返回 None；CLI `show()` 和 Streamlit `app.py` 展示层已适配多场景和 None 返回值
- 2026-07-02：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-02：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，6 个规则层测试全部通过
- 2026-07-02：`.venv\Scripts\python.exe main.py --no-plot` 通过，563360 缩量偏强，无买入场景触发（RSI 57 正常）
- 2026-07-02：`.venv\Scripts\python.exe main.py --symbol 588000 --no-plot` 通过，588000 高位放量过热
- 2026-07-02：`.venv\Scripts\python.exe main.py --symbol 518880 --no-plot` 通过，黄金弱势下行 RSI=30（等于阈值不触发）
- 2026-07-02：`.venv\Scripts\python.exe main.py --symbol 510300 --no-plot` 通过，510300 缩量偏强
- 2026-07-02：买入条件检查重构五项改动：①优先级调整为 健康回踩 → RSI低位修复 → 放量突破 ②新增统一风险否决 `_risk_veto()`（放量破位/弱势下行/严重过热/高位放量过热/MA60下方趋势未修复） ③RSI低位买入 → RSI低位修复买入（过去10日曾低位 + 当前修复确认，不再要求当前RSI低位同时站上MA20） ④健康回踩去强制当日收跌，条件5→4条（移除"回踩确认"） ⑤放量突破加"不远离均线"，条件5→6条
- 2026-07-02：`.venv\Scripts\python.exe -m py_compile main.py data.py indicators.py dashboard.py chart.py app.py backtest.py` 通过
- 2026-07-02：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，22 个测试全部通过（6 旧 + 7 风险否决 + 9 买入清单重构）
- 2026-07-02：四个 ETF CLI 全部通过；588000 高位放量过热被风险否决、518880 弱势下行被风险否决——买入清单均正确抑制
- 2026-07-02：Streamlit 页面 `http://127.0.0.1:8501` 返回 200
- 2026-07-03：新增 `validate_text.py`，文案-数据一致性自动验证系统，覆盖 7 大类规则（状态标签/步骤状态/一句话/关键词/提醒/买入清单/操作理解），CLI 和 Streamlit 均接入
- 2026-07-03：`.venv\Scripts\python.exe -m py_compile` 全部文件通过
- 2026-07-03：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，22 个测试全部通过
- 2026-07-03：四个 ETF CLI 全部通过；518880 ADX 提醒中"RSI低位"模板文案与当前 RSI=46 矛盾（已知遗留模板问题，验证层正确捕获）
- 2026-07-03：Streamlit 页面 `http://127.0.0.1:8501` 返回 200，验证区块仅在发现问题时显示
- 2026-07-03：重构 `validate_text.py`——①`derive_expected_state(d)` 按优先级推导预期状态，对比页面输出 ②中性观察也校验 ③`derive_expected_buy_scenario()` 校验买入清单场景缺失/不一致 ④`_recheck_condition` 全条件修复（曾入低位/无量恐慌/不远离均线等）⑤`_collect_text` 只收集 ok=True 条件，ok=False 标记"未满足" ⑥关键词降级为弱提醒 ⑦同义词映射（红柱为正≈上涨动能占优≈MACD偏多）
- 2026-07-03：`.venv\Scripts\python.exe -m py_compile` 全部文件通过
- 2026-07-03：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，22 个测试全部通过
- 2026-07-04：修复状态分类优先级 bug——"尝试修复"（MA20下方收涨+MACD改善）现优先于"趋势偏弱"（DIF<DEA）；同时修复 `validate_text.py` `derive_expected_state()` 中相同问题；黄金ETF 518880 从"趋势偏弱"正确分类为"尝试修复"
- 2026-07-04：`.venv\Scripts\python.exe -m py_compile` 全部文件通过
- 2026-07-04：`.venv\Scripts\python.exe -m unittest discover -s tests` 通过，22 个测试全部通过
- 2026-07-04：修复 ADX 提醒中 `rsi < 45` 硬编码→改为 `rsi < rsi_buy_threshold`（ETF专属阈值），黄金 ETF RSI=39 不再误触"RSI低位"文案，改为"等待止跌信号，不急于判断底部"
- 2026-07-04：`app.py` 新增 `importlib.reload()` 自动重载机制 + `start_app.ps1` 新增 `--server.runOnSave=true`；改代码后刷新页面即生效，不再需要手动重启 Streamlit
- 2026-07-04：新增 `journal.py` 交易日志系统——`create_entry()` 自动抓当日指标生成 MD 日志，`list_entries()` 浏览历史，`review()` 拉实际数据回填预测对比；日志存储于 `journal/{symbol}/{date}.md`
- 2026-07-04：`.venv\Scripts\python.exe -m py_compile journal.py` 通过
- 2026-07-04：创建 `journal/518880/trades.csv`（黄金22笔）、`journal/603993/trades.csv`（洛阳钼业36笔）、`journal/HSI/trades.csv`（恒生ETF 26笔）、`journal/HSTECH/trades.csv`（恒生科技20笔）
- 2026-07-04：四只持仓交易分析脚本 `scripts/trade_analysis.py`、`trade_603993.py`、`trade_hsi.py`、`trade_hstech.py` 全部通过
- 2026-07-04：创建 `journal/错题本.md`——四只标的18个月98笔交易完整回顾，总结四大重复错误（低位少高位多、不止损、恐慌日反复操作、长期投资当追高借口），五条铁律
- 2026-07-04：新增 `_personalized_warnings()` 错题本警告函数（后从 `_reminders()` 撤下，保留代码供回测参考）
- 2026-07-04：创建 `scripts/replay_mistakes.py` 六笔关键高位买入复盘 + `scripts/replay_603993.py` 洛阳钼业专项复盘 + `scripts/backtest_warnings.py` 全历史回测
- 2026-07-04：回测结论——错题本警告在强牛市中方向性差（触发率43-79%，假阳性47-75%），无法区分"健康新高"和"顶部崩塌"；达达要求工具保持客观专业、不涉及情绪或个人历史，已从 dashboard 移除个性化提醒
- 2026-07-04：修复错题本黄金数据——最贵买入10.921（2026-02-27,1000份），最大仓位9.170（2026-03-23,4600份）；发现9.170暴跌后低位买入反而是好交易（30日+9.1%）
- 2026-07-04：`.venv\Scripts\python.exe -m py_compile dashboard.py` 通过；`.venv\Scripts\python.exe -m unittest discover -s tests` 全部通过
