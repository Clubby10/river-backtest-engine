import threading
from tkinter import messagebox

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from backtest_builder import build_engine_and_data
from strategies.rsi_reversion import RSIReversion
from strategies.sma_crossover import SMACrossover
from utils import draw_backtest_chart


class BacktestGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("River Backtest Studio")
        self.geometry("1400x860")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._build_layout()
        self._build_controls()
        self._build_results_panel()

        self.current_results = None

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.controls_panel = ctk.CTkFrame(self, corner_radius=10)
        self.controls_panel.grid(row=0, column=0, sticky="ns", padx=(12, 6), pady=12)

        self.results_panel = ctk.CTkFrame(self, corner_radius=10)
        self.results_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

    def _build_controls(self) -> None:
        panel = self.controls_panel
        ctk.CTkLabel(panel, text="Backtest Controls", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="ew", pady=(10, 12), padx=16)

        self.notebook = ctk.CTkTabview(panel)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        panel.grid_rowconfigure(1, weight=1)

        self.tab_assets = self.notebook.add("Assets & General")
        self.tab_strategy = self.notebook.add("Strategy")
        self.tab_risk = self.notebook.add("Risk Management")

        self.inputs = {}
        self._build_assets_tab()
        self._build_strategy_tab()
        self._build_risk_tab()

        self.run_btn = ctk.CTkButton(panel, text="Run Backtest", command=self._run_clicked, font=("Segoe UI", 14, "bold"), height=40)
        self.run_btn.grid(row=2, column=0, sticky="ew", padx=16)

        self.status_var = ctk.StringVar(value="Ready")
        ctk.CTkLabel(panel, textvariable=self.status_var, font=("Segoe UI", 12)).grid(row=3, column=0, sticky="w", padx=16, pady=(10, 10))

    def _build_assets_tab(self) -> None:
        tab = self.tab_assets
        
        # General Settings
        gen_frame = ctk.CTkFrame(tab)
        gen_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(gen_frame, text="General Settings", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        
        row = 1
        for label, key, default in [
            ("Start Date", "start_date", "2018-01-01"),
            ("Initial Capital", "initial_capital", "10000"),
            ("Commission", "commission", "2.0"),
            ("Slippage", "slippage", "0.0001"),
        ]:
            ctk.CTkLabel(gen_frame, text=label, font=("Segoe UI", 12)).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            entry = ctk.CTkEntry(gen_frame, width=120)
            entry.insert(0, default)
            entry.grid(row=row, column=1, sticky="e", padx=10, pady=4)
            self.inputs[key] = entry
            row += 1

        # Dynamic Assets
        self.assets_frame = ctk.CTkFrame(tab)
        self.assets_frame.pack(fill="both", expand=True)
        
        header_frame = ctk.CTkFrame(self.assets_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 8), padx=10)
        ctk.CTkLabel(header_frame, text="Assets Portfolio", font=("Segoe UI", 14, "bold")).pack(side="left")
        
        add_btn = ctk.CTkButton(header_frame, text="+ Add Ticker", width=80, command=self._add_asset_row)
        add_btn.pack(side="right")

        self.asset_rows_container = ctk.CTkFrame(self.assets_frame, fg_color="transparent")
        self.asset_rows_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        ctk.CTkLabel(self.asset_rows_container, text="Ticker", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 4))
        ctk.CTkLabel(self.asset_rows_container, text="Allocation", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=(0, 4))
        
        self.asset_rows = []
        # Add initial defaults
        for t, a in [("AAPL", "0.34"), ("MSFT", "0.33"), ("NVDA", "0.33")]:
            self._add_asset_row(t, a)

    def _add_asset_row(self, ticker="", alloc="", event=None) -> None:
        row_idx = len(self.asset_rows) + 1
        
        ticker_var = ctk.StringVar(value=ticker)
        alloc_var = ctk.StringVar(value=alloc)
        
        ticker_entry = ctk.CTkEntry(self.asset_rows_container, textvariable=ticker_var, width=100)
        ticker_entry.grid(row=row_idx, column=0, pady=4, padx=(0, 8))
        
        alloc_entry = ctk.CTkEntry(self.asset_rows_container, textvariable=alloc_var, width=100)
        alloc_entry.grid(row=row_idx, column=1, pady=4, padx=(0, 8))
        
        remove_btn = ctk.CTkButton(self.asset_rows_container, text="X", width=30, fg_color="#ef4444", hover_color="#dc2626",
                                command=lambda r=row_idx: self._remove_asset_row(r))
        remove_btn.grid(row=row_idx, column=2, pady=4)
        
        # Bind Enter to add a new row
        ticker_entry.bind("<Return>", self._add_asset_row)
        alloc_entry.bind("<Return>", self._add_asset_row)
        
        self.asset_rows.append({
            "id": row_idx,
            "ticker_var": ticker_var,
            "alloc_var": alloc_var,
            "ticker_entry": ticker_entry,
            "alloc_entry": alloc_entry,
            "remove_btn": remove_btn
        })
        ticker_entry.focus_set()

    def _remove_asset_row(self, row_id: int) -> None:
        for item in self.asset_rows:
            if item["id"] == row_id:
                item["ticker_entry"].destroy()
                item["alloc_entry"].destroy()
                item["remove_btn"].destroy()
                self.asset_rows.remove(item)
                break

    def _build_strategy_tab(self) -> None:
        tab = self.tab_strategy
        
        ctk.CTkLabel(tab, text="Position Size", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", pady=(10, 2), padx=10)
        pos_entry = ctk.CTkEntry(tab)
        pos_entry.insert(0, "0.50")
        pos_entry.grid(row=1, column=0, sticky="ew", pady=(0, 12), padx=10)
        self.inputs["position_size"] = pos_entry
        
        ctk.CTkLabel(tab, text="Strategy", font=("Segoe UI", 12)).grid(row=2, column=0, sticky="w", pady=(0, 2), padx=10)
        self.strategy_var = ctk.StringVar(value="SMA Crossover")
        strategy_combo = ctk.CTkComboBox(tab, variable=self.strategy_var, values=["SMA Crossover", "RSI Reversion"], command=self._toggle_strategy_params)
        strategy_combo.grid(row=3, column=0, sticky="ew", pady=(0, 12), padx=10)
        
        self.sma_frame = ctk.CTkFrame(tab)
        ctk.CTkLabel(self.sma_frame, text="SMA Short", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=10, pady=(10,0))
        self.sma_short = ctk.CTkEntry(self.sma_frame)
        self.sma_short.insert(0, "20")
        self.sma_short.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        ctk.CTkLabel(self.sma_frame, text="SMA Long", font=("Segoe UI", 12)).grid(row=2, column=0, sticky="w", padx=10)
        self.sma_long = ctk.CTkEntry(self.sma_frame)
        self.sma_long.insert(0, "50")
        self.sma_long.grid(row=3, column=0, sticky="w", padx=10, pady=(0,10))

        self.rsi_frame = ctk.CTkFrame(tab)
        ctk.CTkLabel(self.rsi_frame, text="RSI Period", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=10, pady=(10,0))
        self.rsi_period = ctk.CTkEntry(self.rsi_frame)
        self.rsi_period.insert(0, "14")
        self.rsi_period.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        ctk.CTkLabel(self.rsi_frame, text="RSI Oversold", font=("Segoe UI", 12)).grid(row=2, column=0, sticky="w", padx=10)
        self.rsi_oversold = ctk.CTkEntry(self.rsi_frame)
        self.rsi_oversold.insert(0, "30")
        self.rsi_oversold.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 8))
        ctk.CTkLabel(self.rsi_frame, text="RSI Overbought", font=("Segoe UI", 12)).grid(row=4, column=0, sticky="w", padx=10)
        self.rsi_overbought = ctk.CTkEntry(self.rsi_frame)
        self.rsi_overbought.insert(0, "70")
        self.rsi_overbought.grid(row=5, column=0, sticky="w", padx=10, pady=(0,10))

        self.sma_frame.grid(row=4, column=0, sticky="ew", padx=10)

    def _build_risk_tab(self) -> None:
        tab = self.tab_risk
        
        row = 0
        for label, key, default in [
            ("Stop Loss %", "stop_loss_pct", "0.25"),
            ("Take Profit %", "take_profit_pct", "0.50"),
            ("Max DD Cutoff %", "max_drawdown_cutoff_pct", "0.20"),
            ("Kelly Lookback", "kelly_lookback", "20"),
            ("Kelly Min Trades", "kelly_min_trades", "10"),
            ("Kelly p (optional)", "kelly_p", ""),
            ("Kelly b (optional)", "kelly_b", ""),
        ]:
            ctk.CTkLabel(tab, text=label, font=("Segoe UI", 12)).grid(row=row, column=0, sticky="w", pady=(8, 0), padx=10)
            entry = ctk.CTkEntry(tab)
            entry.insert(0, default)
            entry.grid(row=row+1, column=0, sticky="ew", pady=(0, 2), padx=10)
            self.inputs[key] = entry
            row += 2

        self.use_rolling_kelly = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            tab,
            text="Use Rolling Kelly",
            variable=self.use_rolling_kelly,
        ).grid(row=row, column=0, sticky="w", pady=(12, 0), padx=10)

    def _build_results_panel(self) -> None:
        panel = self.results_panel
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        metric_card = ctk.CTkFrame(panel)
        metric_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.metric_vars = {}
        metric_keys = [
            ("Total Return", "total_return_pct"),
            ("Sharpe", "sharpe_ratio"),
            ("Max Drawdown", "max_drawdown_pct"),
            ("Calmar", "calmar_ratio"),
            ("Win Rate", "win_rate_pct"),
            ("Benchmark", "benchmark_return_pct"),
            ("Vs Benchmark", "outperformance_vs_benchmark_pct"),
        ]
        for idx, (label, key) in enumerate(metric_keys):
            ctk.CTkLabel(metric_card, text=label, font=("Segoe UI", 12, "bold")).grid(row=0, column=idx, sticky="w", padx=(16, 12), pady=(10,0))
            var = ctk.StringVar(value="-")
            ctk.CTkLabel(metric_card, textvariable=var, font=("Segoe UI", 16, "bold"), text_color="#38bdf8").grid(row=1, column=idx, sticky="w", padx=(16, 12), pady=(0,10))
            self.metric_vars[key] = var

        self.show_benchmark_var = ctk.BooleanVar(value=False)
        self.normalize_benchmark_var = ctk.BooleanVar(value=True)

        ctk.CTkCheckBox(
            metric_card,
            text="Show Benchmark",
            variable=self.show_benchmark_var,
            command=self._redraw_from_current_results,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=(16, 8), pady=(0, 10))

        ctk.CTkCheckBox(
            metric_card,
            text="Normalize Benchmark",
            variable=self.normalize_benchmark_var,
            command=self._redraw_from_current_results,
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=(8, 8), pady=(0, 10))

        chart_card = ctk.CTkFrame(panel)
        chart_card.grid(row=1, column=0, sticky="nsew")
        chart_card.grid_rowconfigure(0, weight=1)
        chart_card.grid_columnconfigure(0, weight=1)

        self.figure = plt.Figure(figsize=(10, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#1e293b")
        self.figure.patch.set_facecolor("#0f172a")
        self.ax.tick_params(colors="#d1d5db")
        self.ax.set_title("Portfolio Backtest", color="#f9fafb")

        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_card)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

    def _toggle_strategy_params(self, _choice=None) -> None:
        choice = self.strategy_var.get()
        self.sma_frame.grid_remove()
        self.rsi_frame.grid_remove()
        if choice == "SMA Crossover":
            self.sma_frame.grid()
        else:
            self.rsi_frame.grid()

    def _optional_float(self, value: str):
        value = value.strip()
        return None if value == "" else float(value)

    def _build_strategy(self):
        if self.strategy_var.get() == "SMA Crossover":
            return SMACrossover(short_window=int(self.sma_short.get()), long_window=int(self.sma_long.get()))
        return RSIReversion(
            period=int(self.rsi_period.get()),
            oversold=float(self.rsi_oversold.get()),
            overbought=float(self.rsi_overbought.get())
        )

    def _run_clicked(self) -> None:
        self.run_btn.configure(state="disabled")
        self.status_var.set("Running backtest...")
        threading.Thread(target=self._run_backtest, daemon=True).start()

    def _run_backtest(self) -> None:
        try:
            tickers = []
            allocations = {}

            for row_data in self.asset_rows:
                t = row_data["ticker_var"].get().strip().upper()
                a_str = row_data["alloc_var"].get().strip()
                if t and a_str:
                    tickers.append(t)
                    allocations[t] = float(a_str)

            if not tickers:
                raise ValueError("Please provide at least one valid ticker and allocation.")

            engine, portfolio_data, cleaned_tickers, _ = build_engine_and_data(
                strategy=self._build_strategy(),
                tickers=tickers,
                start_date=self.inputs["start_date"].get().strip(),
                initial_capital=float(self.inputs["initial_capital"].get()),
                commission=float(self.inputs["commission"].get()),
                slippage=float(self.inputs["slippage"].get()),
                position_size=float(self.inputs["position_size"].get()),
                kelly_p=self._optional_float(self.inputs["kelly_p"].get()),
                kelly_b=self._optional_float(self.inputs["kelly_b"].get()),
                use_rolling_kelly=self.use_rolling_kelly.get(),
                kelly_lookback=int(self.inputs["kelly_lookback"].get()),
                kelly_min_trades=int(self.inputs["kelly_min_trades"].get()),
                stop_loss_pct=self._optional_float(self.inputs["stop_loss_pct"].get()),
                take_profit_pct=self._optional_float(self.inputs["take_profit_pct"].get()),
                max_drawdown_cutoff_pct=self._optional_float(self.inputs["max_drawdown_cutoff_pct"].get()),
                allocations=allocations,
                show_download_progress=False,
            )

            results = engine.run(portfolio_data)
            self.current_results = results
            self.after(0, lambda: self._render_results(cleaned_tickers, results))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Backtest Error", str(exc)))
            self.after(0, lambda: self.status_var.set("Error. Adjust parameters and try again."))
        finally:
            self.after(0, lambda: self.run_btn.configure(state="normal"))

    def _redraw_from_current_results(self) -> None:
        if self.current_results is None:
            return

        trades_df = self.current_results.get("trades")
        if trades_df is not None and not trades_df.empty and "ticker" in trades_df.columns:
            tickers = list(dict.fromkeys(trades_df["ticker"].astype(str).tolist()))
        else:
            ticker_values = self.current_results.get("ticker_value_curve")
            tickers = list(ticker_values.columns) if ticker_values is not None else ["Portfolio"]

        self._render_results(tickers, self.current_results)

    def _render_results(self, tickers: list[str], results: dict) -> None:
        metrics = results["metrics"]
        self.metric_vars["total_return_pct"].set(f"{metrics.get('total_return_pct', 0)}%")
        self.metric_vars["sharpe_ratio"].set(f"{metrics.get('sharpe_ratio', 0)}")
        self.metric_vars["max_drawdown_pct"].set(f"{metrics.get('max_drawdown_pct', 0)}%")
        self.metric_vars["calmar_ratio"].set(f"{metrics.get('calmar_ratio', 0)}")
        self.metric_vars["win_rate_pct"].set(f"{metrics.get('win_rate_pct', 0)}%")
        self.metric_vars["benchmark_return_pct"].set(f"{metrics.get('benchmark_return_pct', 0)}%")
        self.metric_vars["outperformance_vs_benchmark_pct"].set(f"{metrics.get('outperformance_vs_benchmark_pct', 0)}%")

        equity_curve = results["equity_curve"]
        ticker_values = results["ticker_value_curve"]
        benchmark_curve = results.get("benchmark_curve")

        draw_backtest_chart(
            ax=self.ax,
            equity_curve=equity_curve,
            ticker=", ".join(tickers),
            ticker_value_curve=ticker_values,
            benchmark_curve=benchmark_curve,
            show_benchmark=self.show_benchmark_var.get(),
            normalize_benchmark=self.normalize_benchmark_var.get(),
        )

        self.canvas.draw_idle()
        self.status_var.set("Backtest complete. Update params and run again.")


if __name__ == "__main__":
    app = BacktestGUI()
    app.mainloop()
