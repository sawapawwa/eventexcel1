import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from scrape import scrape_urls, save_to_excel, load_urls_file


class ScraperGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Baltimore Events Scraper")
        self.geometry("640x420")

        self.urls_path_var = tk.StringVar()
        self.output_var = tk.StringVar(value="baltimore_events.xlsx")
        self.delay_var = tk.StringVar(value="1.0")

        frm = tk.Frame(self)
        frm.pack(padx=10, pady=10, fill=tk.X)

        tk.Label(frm, text="URLs file:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(frm, textvariable=self.urls_path_var, width=50).grid(row=0, column=1)
        tk.Button(frm, text="Browse", command=self.browse_urls).grid(row=0, column=2, padx=6)

        tk.Label(frm, text="Output Excel:").grid(row=1, column=0, sticky=tk.W)
        tk.Entry(frm, textvariable=self.output_var, width=50).grid(row=1, column=1)

        tk.Label(frm, text="Delay (s):").grid(row=2, column=0, sticky=tk.W)
        tk.Entry(frm, textvariable=self.delay_var, width=10).grid(row=2, column=1, sticky=tk.W)

        tk.Button(frm, text="Run Scraper", command=self.start_scrape).grid(row=3, column=1, pady=8)

        self.log = scrolledtext.ScrolledText(self, height=14)
        self.log.pack(padx=10, pady=(0,10), fill=tk.BOTH, expand=True)

    def browse_urls(self):
        p = filedialog.askopenfilename(title="Select URLs file", filetypes=[("Text files","*.txt"), ("All files","*")])
        if p:
            self.urls_path_var.set(p)

    def log_msg(self, msg: str):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.update_idletasks()

    def start_scrape(self):
        urls_path = self.urls_path_var.get().strip()
        if not urls_path:
            messagebox.showwarning("No URLs file", "Please select a URLs file first.")
            return
        try:
            delay = float(self.delay_var.get())
        except Exception:
            messagebox.showwarning("Invalid delay", "Delay must be a number.")
            return

        t = threading.Thread(target=self.run_scraper, args=(urls_path, self.output_var.get(), delay), daemon=True)
        t.start()

    def run_scraper(self, urls_path: str, output: str, delay: float):
        try:
            self.log_msg(f"Loading URLs from {urls_path}...")
            urls = load_urls_file(urls_path)
            self.log_msg(f"Found {len(urls)} seed URLs. Starting scrape...")
            events = scrape_urls(urls, delay=delay)
            self.log_msg(f"Scraped {len(events)} events. Saving to {output}...")
            save_to_excel(events, output)
            self.log_msg("Done — output saved.")
            messagebox.showinfo("Finished", f"Scraping finished. {len(events)} events saved to {output}.")
        except Exception as e:
            self.log_msg("Error during scraping:")
            self.log_msg(str(e))
            self.log_msg(traceback.format_exc())
            messagebox.showerror("Error", f"An error occurred: {e}")


if __name__ == "__main__":
    app = ScraperGUI()
    app.mainloop()
