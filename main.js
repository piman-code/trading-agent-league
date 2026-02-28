"use strict";

const { Plugin, Notice, Modal, Setting } = require("obsidian");

class RoundModal extends Modal {
  constructor(app, onSubmit) {
    super(app);
    this.onSubmit = onSubmit;
    this.league = "Trading Agent League";
    this.round = 1;
    this.participants = "Alpha,Beta,Gamma";
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "리그 라운드 노트 생성" });

    new Setting(contentEl)
      .setName("리그 이름")
      .addText((t) => t.setValue(this.league).onChange((v) => (this.league = v || "Trading Agent League")));

    new Setting(contentEl)
      .setName("라운드")
      .addText((t) =>
        t.setValue(String(this.round)).onChange((v) => {
          const n = Number(v);
          this.round = Number.isFinite(n) && n > 0 ? Math.floor(n) : 1;
        })
      );

    new Setting(contentEl)
      .setName("참가자 (쉼표 구분)")
      .addTextArea((a) => a.setValue(this.participants).onChange((v) => (this.participants = v)));

    new Setting(contentEl).addButton((b) =>
      b.setButtonText("생성").setCta().onClick(() => {
        const participants = this.participants.split(",").map((x) => x.trim()).filter(Boolean);
        this.onSubmit({ league: this.league, round: this.round, participants });
        this.close();
      })
    );
  }

  onClose() {
    this.contentEl.empty();
  }
}

module.exports = class TradingAgentLeaguePlugin extends Plugin {
  async onload() {
    this.addCommand({
      id: "tal-create-round-note",
      name: "TAL: 라운드 노트 생성",
      callback: () => this.openRoundModal(),
    });

    this.addCommand({
      id: "tal-generate-standings",
      name: "TAL: Results에서 순위표 생성",
      editorCallback: (editor) => {
        const table = this.resultsToStandings(editor.getValue());
        if (!table) return new Notice("`## Results`에서 파싱 가능한 결과를 찾지 못했습니다.");
        editor.replaceSelection(`\n\n## Standings\n\n${table}\n`);
        new Notice("순위표 삽입 완료");
      },
    });
  }

  openRoundModal() {
    new RoundModal(this.app, async ({ league, round, participants }) => {
      const active = this.app.workspace.getActiveFile();
      const base = active ? active.parent.path : "";
      const safe = league.replace(/[\\/:*?"<>|]/g, "-").trim();
      const path = `${base ? base + "/" : ""}${safe}-R${round}.md`;
      const content = this.roundTemplate(league, round, participants);
      try {
        const file = await this.app.vault.create(path, content);
        await this.app.workspace.getLeaf(true).openFile(file);
        new Notice(`생성됨: ${path}`);
      } catch (e) {
        new Notice(`실패: ${e.message}`);
      }
    }).open();
  }

  roundTemplate(league, round, participants) {
    const p = participants.length ? participants : ["Alpha", "Beta", "Gamma"];
    return `---
league: ${league}
round: ${round}
created: ${new Date().toISOString()}
---

# ${league} Round ${round}

## Participants
${p.map((x) => `- ${x}`).join("\n")}

## Results
${p.map((x) => `- ${x}: 0.00%`).join("\n")}

## Notes
- strategy
- risk events
`;
  }

  resultsToStandings(markdown) {
    const sec = markdown.match(/## Results([\s\S]*?)(\n## |$)/i);
    if (!sec) return null;
    const rows = sec[1]
      .split("\n")
      .map((l) => l.trim())
      .map((l) => l.match(/^-\s*(.+?)\s*:\s*([+-]?\d+(?:\.\d+)?)\s*%?\s*$/))
      .filter(Boolean)
      .map((m) => ({ name: m[1], ret: Number(m[2]) }));

    if (!rows.length) return null;
    rows.sort((a, b) => b.ret - a.ret);

    return [
      "| Rank | Agent | Return |",
      "|---:|---|---:|",
      ...rows.map((r, i) => `| ${i + 1} | ${r.name} | ${r.ret.toFixed(2)}% |`),
    ].join("\n");
  }
};
