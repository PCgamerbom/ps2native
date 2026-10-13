"""Interface gráfica (PySide6). Requer: pip install PySide6"""
from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from .analysis import IsoReport, analyze_iso
from .package import CLASSIFICACAO, build_package, can_package
from .report import to_json, to_markdown

STYLE = """
QMainWindow, QWidget { background: #14161b; color: #e6e8ee; font-size: 13px; }
QLineEdit, QPlainTextEdit, QTableWidget { background: #1c1f27; border: 1px solid #2c303b;
  border-radius: 6px; padding: 4px; gridline-color: #2c303b; }
QHeaderView::section { background: #232733; color: #aab0c0; border: none; padding: 6px; }
QPushButton { background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 8px 14px; }
QPushButton:disabled { background: #2c303b; color: #777d8c; }
QPushButton:hover:!disabled { background: #5b9bff; }
QTabBar::tab { background: #1c1f27; padding: 8px 14px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #2a2f3d; }
QProgressBar { border: 1px solid #2c303b; border-radius: 6px; text-align: center; background: #1c1f27; }
QProgressBar::chunk { background: #3b82f6; border-radius: 5px; }
"""

STAGES = ["Abrindo imagem ISO9660", "Listando arquivos", "Lendo cabeçalhos ELF",
          "Desmontando segmentos executáveis", "Descobrindo funções",
          "Traduzindo funções (subconjunto suportado)", "Concluído"]


class Worker(QThread):
    progress = Signal(str, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self) -> None:  # executa fora da thread da UI; nunca executa código da ISO
        try:
            rep = analyze_iso(self.path, lambda s, p: self.progress.emit(s, p))
            self.done.emit(rep)
        except Exception as e:  # noqa: BLE001 - mostramos qualquer erro ao usuário
            self.failed.emit(f"{type(e).__name__}: {e}")


def _table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return t


def _fill(t: QTableWidget, rows) -> None:
    t.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            t.setItem(i, j, QTableWidgetItem(str(v)))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PS2Native — protótipo experimental")
        self.resize(1000, 700)
        self.report: Optional[IsoReport] = None
        self.worker: Optional[Worker] = None

        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        top = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setPlaceholderText("Selecione uma imagem ISO de PS2…")
        self.path.setReadOnly(True)
        b_pick = QPushButton("Selecionar ISO…")
        b_pick.clicked.connect(self.pick)
        top.addWidget(self.path, 1)
        top.addWidget(b_pick)
        v.addLayout(top)

        self.stage = QLabel("Aguardando ISO.")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        v.addWidget(self.stage)
        v.addWidget(self.bar)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        self.tabs = QTabWidget()
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.t_exec = _table(["Caminho", "Formato", "Tamanho (bytes)", "Principal"])
        self.t_funcs = _table(["Entrada", "Nome", "Instruções", "Status", "Não suportadas"])
        self.t_unsup = _table(["Instrução — motivo", "Ocorrências"])
        self.full = QPlainTextEdit()
        self.full.setReadOnly(True)
        self.tabs.addTab(self.summary, "Resumo")
        self.tabs.addTab(self.t_exec, "Executáveis")
        self.tabs.addTab(self.t_funcs, "Funções")
        self.tabs.addTab(self.t_unsup, "Não suportado")
        self.tabs.addTab(self.full, "Relatório completo")
        v.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        self.b_export = QPushButton("Exportar relatório…")
        self.b_export.clicked.connect(self.export)
        self.b_pkg = QPushButton("Gerar pacote (análise/protótipo)…")
        self.b_pkg.clicked.connect(self.package)
        self.b_export.setEnabled(False)
        self.b_pkg.setEnabled(False)
        bottom.addStretch(1)
        bottom.addWidget(self.b_export)
        bottom.addWidget(self.b_pkg)
        v.addLayout(bottom)

    # -- ações ---------------------------------------------------------------------
    def pick(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Selecionar ISO", "", "Imagens (*.iso *.bin *.img);;Todos (*)")
        if p:
            self.path.setText(p)
            self.start(p)  # análise automática

    def start(self, p: str) -> None:
        self.b_export.setEnabled(False)
        self.b_pkg.setEnabled(False)
        self.bar.setValue(0)
        self.status.setText("")
        self.worker = Worker(p)
        self.worker.progress.connect(lambda s, n: (self.stage.setText(s), self.bar.setValue(n)))
        self.worker.done.connect(self.finished)
        self.worker.failed.connect(self.error)
        self.worker.start()

    def error(self, msg: str) -> None:
        self.stage.setText("Erro")
        QMessageBox.critical(self, "Falha na análise", msg)

    def finished(self, rep: IsoReport) -> None:
        self.report = rep
        self.stage.setText("Análise concluída.")
        main_path = rep.main_executable["path"] if rep.main_executable else None
        _fill(self.t_exec, [(e["path"], e["format"], e["size"], "sim" if e["path"] == main_path else "")
                            for e in rep.executables])
        a = rep.elf
        if a:
            _fill(self.t_funcs, [(f"0x{f.entry:08x}", f.name, f.n_insns, f.status, f.n_unsupported)
                                 for f in a.functions])
            _fill(self.t_unsup, list(a.unsupported_summary.items()))
            self.status.setText(
                f"<b>Status da portabilidade: nível {a.port_level}/3 — {a.port_label}</b><br>"
                f"Compatibilidade estimada de <i>tradução estática</i>: {a.translated_pct}% das instruções "
                f"das funções descobertas. Compatibilidade de <i>execução</i> do jogo: NÃO validada.")
        else:
            self.t_funcs.setRowCount(0)
            self.t_unsup.setRowCount(0)
            self.status.setText("Nenhum ELF principal analisável. " + " ".join(rep.warnings))
        md = to_markdown(rep)
        self.summary.setPlainText(
            f"Plataforma: {rep.platform}\nVolume: {rep.volume_id}\nBoot: {rep.boot_path}\n"
            f"Arquivos: {rep.n_files}  Diretórios: {rep.n_dirs}\n"
            + ("\nAvisos:\n- " + "\n- ".join(rep.warnings) if rep.warnings else ""))
        self.full.setPlainText(md)
        self.b_export.setEnabled(True)
        self.b_pkg.setEnabled(bool(a and can_package(a)))

    def export(self) -> None:
        if not self.report:
            return
        p, flt = QFileDialog.getSaveFileName(self, "Exportar relatório", "relatorio_ps2native.md",
                                             "Markdown (*.md);;JSON (*.json)")
        if not p:
            return
        text = to_json(self.report) if p.lower().endswith(".json") else to_markdown(self.report)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def package(self) -> None:
        a = self.report.elf if self.report else None
        if not a or not can_package(a):
            return
        ok = QMessageBox.question(
            self, "Gerar pacote",
            f"Classificação: {CLASSIFICACAO[a.port_level]}\n\nIsto NÃO gera um jogo nativo. Gera código C "
            "das funções traduzidas + runtime mínimo + relatórios. Continuar?")
        if ok != QMessageBox.Yes:
            return
        d = QFileDialog.getExistingDirectory(self, "Pasta de destino")
        if d:
            files = build_package(a, os.path.join(d, "ps2native_package"))
            QMessageBox.information(self, "Pacote gerado", "\n".join(files))


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    return app.exec()
