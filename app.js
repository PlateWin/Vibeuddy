const app = document.querySelector(".app-shell");
const startForm = document.querySelector("#startForm");
const startInput = document.querySelector("#startInput");
const promptForm = document.querySelector("#promptForm");
const promptInput = document.querySelector("#promptInput");
const projectName = document.querySelector("#projectName");
const stateLabel = document.querySelector("#stateLabel");
const stateDescription = document.querySelector("#stateDescription");
const stateIcon = document.querySelector("#stateIcon");
const summaryText = document.querySelector("#summaryText");
const riskText = document.querySelector("#riskText");
const suggestionText = document.querySelector("#suggestionText");
const scoreText = document.querySelector("#scoreText");
const levelText = document.querySelector("#levelText");
const evolveModal = document.querySelector("#evolveModal");
const evolveText = document.querySelector("#evolveText");
const poster = document.querySelector("#poster");
const posterButton = document.querySelector("#posterButton");
const closePoster = document.querySelector("#closePoster");
const posterScore = document.querySelector("#posterScore");
const bestMetric = document.querySelector("#bestMetric");
const weakMetric = document.querySelector("#weakMetric");
const evolveCount = document.querySelector("#evolveCount");
const posterComment = document.querySelector("#posterComment");

const metricNames = {
  clarity: "清晰度",
  completion: "完成度",
  fun: "趣味性",
  stability: "稳定性",
  shareability: "传播性",
};

const stateMeta = {
  egg: ["项目蛋", "输入第一个想法，让项目生命体醒来。", "?"],
  idle: ["稳定生长", "项目正在吸收想法，等待下一次迭代。", ""],
  happy: ["开心成长", "这次输入让项目更清晰、更好玩。", "★"],
  confused: ["有点迷茫", "需求还不够具体，它需要更明确的方向。", "?"],
  injured: ["稳定受伤", "实现风险上升，项目需要先修复可行性。", "!"],
  overload: ["功能过载", "功能堆叠太快，MVP 正在变重。", "!!"],
  evolve: ["进化中", "项目完成一次阶段性突破。", "↑"],
  final: ["完全体", "项目已经形成可展示的宠物报告。", "✓"],
};

const state = {
  started: false,
  turns: 0,
  evolutionStage: 1,
  evolutions: 0,
  petState: "egg",
  score: 42,
  projectTitle: "VibePet Lab",
  metrics: {
    clarity: 42,
    completion: 28,
    fun: 46,
    stability: 52,
    shareability: 34,
  },
};

function clamp(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function getScore(metrics) {
  const values = Object.values(metrics);
  return Math.round(values.reduce((sum, item) => sum + item, 0) / values.length);
}

function pulse() {
  app.classList.remove("pulsing");
  requestAnimationFrame(() => {
    app.classList.add("pulsing");
    window.setTimeout(() => app.classList.remove("pulsing"), 760);
  });
}

function showEvolution(stage) {
  evolveText.textContent = `Lv.${stage} ${stage >= 4 ? "完全体宠物" : "项目宠物"}`;
  evolveModal.classList.add("show");
  window.setTimeout(() => evolveModal.classList.remove("show"), 1250);
}

function inferProjectName(input) {
  const compact = input.replace(/[，。,.!！?？]/g, " ").trim();
  if (!compact) return "VibePet Lab";
  const words = compact.split(/\s+/).slice(0, 8).join(" ");
  return words.length > 22 ? `${words.slice(0, 22)}...` : words;
}

function evaluateInput(input) {
  const text = input.toLowerCase();
  const delta = {
    clarity: 2,
    completion: 3,
    fun: 2,
    stability: 0,
    shareability: 1,
  };

  let petState = "idle";
  let summary = "项目吸收了一次新的想法，整体继续向 Demo 形态靠近。";
  let risk = "当前没有明显风险，可以继续补充关键交互。";
  let suggestion = "下一步可以描述用户完成一次核心体验的完整路径。";

  const isVague = input.trim().length < 8 || /随便|不知道|做个东西|好玩点/.test(text);
  const simplify = /简化|mvp|核心|收敛|压缩|三/.test(text);
  const share = /分享|海报|传播|邀请|裂变|朋友圈|扫码/.test(text);
  const fun = /游戏|宠物|排行榜|抽卡|徽章|动画|互动|社交|惊喜/.test(text);
  const heavy = /实时|地图|多人|ai|大模型|语音|视频|区块链|支付|定位|排行榜/.test(text);
  const techRisk = /数据库|登录|权限|部署|支付|实时|地图|定位|多人/.test(text);
  const finish = /完成|最终|报告|海报|答辩|展示|结束/.test(text);

  if (isVague) {
    petState = "confused";
    delta.clarity -= 8;
    delta.completion -= 2;
    summary = "这次输入比较模糊，项目宠物还不能判断要往哪个方向成长。";
    risk = "目标不清晰会让后续功能判断变得困难。";
    suggestion = "试试输入：“我要做给谁用、解决什么场景、第一轮 Demo 做什么。”";
  }

  if (simplify) {
    petState = "happy";
    delta.clarity += 12;
    delta.completion += 8;
    delta.stability += 10;
    summary = "项目范围被收敛了，宠物更容易看见第一版 Demo 的样子。";
    risk = "范围收敛后，要避免把亮点也一起删掉。";
    suggestion = "建议保留一个最能体现 Vibeuddy 记忆点的反馈动画。";
  }

  if (share) {
    petState = "happy";
    delta.fun += 7;
    delta.shareability += 13;
    delta.completion += 4;
    summary = "项目增加了传播机制，现场展示和赛后分享价值提升。";
    risk = "传播功能可以很亮眼，但不要抢走核心宠物反馈闭环。";
    suggestion = "先做一张可截图的项目宠物报告卡，再考虑更复杂的分享链路。";
  }

  if (fun) {
    petState = petState === "confused" ? "confused" : "happy";
    delta.fun += 10;
    delta.shareability += 4;
    summary = "这次输入强化了养成感和互动感，用户更容易记住项目。";
    risk = "趣味机制增加后，需要检查是否会拖慢 MVP。";
    suggestion = "把最有趣的一点做成回车后的即时反馈。";
  }

  if (heavy) {
    delta.fun += 5;
    delta.completion -= 3;
    delta.stability -= 9;
    if (state.turns > 2 || techRisk) {
      petState = "overload";
      summary = "功能数量继续增加，宠物进入过载状态。";
      risk = "MVP 正在变重，实现范围可能超过黑客松时间。";
      suggestion = "试试输入：“帮我压缩成 3 个核心功能。”";
    }
  }

  if (techRisk && !simplify && petState !== "overload") {
    petState = "injured";
    delta.stability -= 12;
    delta.completion -= 2;
    summary = "这次输入引入了技术风险，宠物的稳定核心开始闪烁。";
    risk = "实时、权限、地图或支付类能力都可能提高实现成本。";
    suggestion = "建议先用假数据或本地状态模拟，保住演示闭环。";
  }

  if (finish || state.turns >= 6) {
    petState = "final";
    delta.clarity += 5;
    delta.completion += 10;
    delta.shareability += 5;
    summary = "项目已经接近可展示形态，可以生成最终宠物报告。";
    risk = "最后阶段重点是打磨展示路径，不再继续加大功能。";
    suggestion = "生成海报，准备用“回车到进化”的闭环进行答辩。";
  }

  const nextMetrics = {};
  Object.entries(state.metrics).forEach(([key, value]) => {
    nextMetrics[key] = clamp(value + delta[key]);
  });

  const nextScore = getScore(nextMetrics);
  let evolutionStage = state.evolutionStage;
  let evolved = false;

  if (nextScore >= 56 && evolutionStage < 2) {
    evolutionStage = 2;
    evolved = true;
  } else if (nextScore >= 70 && evolutionStage < 3) {
    evolutionStage = 3;
    evolved = true;
  } else if (nextScore >= 82 && evolutionStage < 4) {
    evolutionStage = 4;
    evolved = true;
    petState = "final";
  }

  if (evolved && petState !== "final") {
    petState = "evolve";
    summary = "项目达成关键成长节点，宠物触发进化。";
    risk = "进化后可以继续加强一个核心亮点，避免横向发散。";
    suggestion = "下一步补充一条最适合现场展示的用户路径。";
  }

  return {
    petState,
    evolutionStage,
    evolved,
    score: nextScore,
    metrics: nextMetrics,
    delta,
    summary,
    risk,
    suggestion,
  };
}

function updateMetrics(delta = {}) {
  Object.entries(state.metrics).forEach(([key, value]) => {
    const row = document.querySelector(`.metric[data-metric="${key}"]`);
    const strong = row.querySelector("strong");
    const bar = row.querySelector(".bar span");
    row.classList.remove("delta-up", "delta-down");
    if (delta[key] > 0) row.classList.add("delta-up");
    if (delta[key] < 0) row.classList.add("delta-down");
    strong.textContent = value;
    bar.style.width = `${value}%`;
  });
}

function render(result = {}) {
  app.dataset.state = state.petState;
  projectName.textContent = state.projectTitle;
  scoreText.textContent = state.score;
  levelText.textContent = `Lv.${state.evolutionStage}`;

  const meta = stateMeta[state.petState] || stateMeta.idle;
  stateLabel.textContent = meta[0];
  stateDescription.textContent = meta[1];
  stateIcon.textContent = meta[2];

  summaryText.textContent = result.summary || summaryText.textContent;
  riskText.textContent = result.risk || riskText.textContent;
  suggestionText.textContent = result.suggestion || suggestionText.textContent;

  updateMetrics(result.delta);
  updatePoster();
}

function updatePoster() {
  const entries = Object.entries(state.metrics);
  const best = entries.reduce((winner, item) => (item[1] > winner[1] ? item : winner), entries[0]);
  const weak = entries.reduce((loser, item) => (item[1] < loser[1] ? item : loser), entries[0]);

  posterScore.textContent = state.score;
  bestMetric.textContent = metricNames[best[0]];
  weakMetric.textContent = metricNames[weak[0]];
  evolveCount.textContent = state.evolutions;

  if (state.score >= 82) {
    posterComment.textContent = "这是一只接近完全体的项目宠物。它有清晰的展示路径，也具备不错的传播潜力。";
  } else if (weak[0] === "stability") {
    posterComment.textContent = "这个项目很有趣，但需要收敛技术范围，先让核心闭环稳定跑起来。";
  } else {
    posterComment.textContent = "这个项目正在变得更具体。继续输入，让宠物完成下一次进化。";
  }
}

function applyResult(input, result) {
  state.turns += 1;
  state.petState = result.petState;
  state.evolutionStage = result.evolutionStage;
  state.score = result.score;
  state.metrics = result.metrics;

  if (!state.started) {
    state.started = true;
    state.projectTitle = inferProjectName(input);
    app.classList.add("started");
    document.querySelector("#workspace").setAttribute("aria-hidden", "false");
  }

  if (result.evolved) {
    state.evolutions += 1;
    showEvolution(result.evolutionStage);
  }

  pulse();
  render(result);

  if (result.petState === "evolve") {
    window.setTimeout(() => {
      state.petState = "happy";
      render({
        summary: "进化完成。宠物进入开心成长状态，等待下一次输入。",
        risk: result.risk,
        suggestion: result.suggestion,
      });
    }, 1400);
  }
}

function handleInput(input) {
  const value = input.trim();
  if (!value) return;
  const result = evaluateInput(value);
  applyResult(value, result);
}

startForm.addEventListener("submit", (event) => {
  event.preventDefault();
  handleInput(startInput.value);
  startInput.value = "";
  window.setTimeout(() => promptInput.focus(), 480);
});

promptForm.addEventListener("submit", (event) => {
  event.preventDefault();
  handleInput(promptInput.value);
  promptInput.value = "";
});

posterButton.addEventListener("click", () => {
  state.petState = state.score >= 78 ? "final" : state.petState;
  render({
    summary: "已生成项目宠物报告卡。",
    risk: riskText.textContent,
    suggestion: "用这张报告卡作为答辩结尾，会更容易被记住。",
  });
  poster.classList.add("show");
  poster.setAttribute("aria-hidden", "false");
});

closePoster.addEventListener("click", () => {
  poster.classList.remove("show");
  poster.setAttribute("aria-hidden", "true");
});

render();
