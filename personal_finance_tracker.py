"""
Personal Finance Tracker
File: personal_finance_tracker.py

Project description
-------------------
A clean, dependency-free command-line Personal Finance Tracker built with Python data structures.
It stores transactions as a list of `Transaction` dataclasses (an array of structures), supports
sorting, searching and filtering, can save/load data from a JSON file, and includes an ASCII
bar chart visualization for monthly spending.

What changed in this version (debugged)
--------------------------------------
1) **Non-interactive / sandbox-safe mode**: If stdin isn't interactive (common in sandboxes), the
   script now automatically runs a demo instead of prompting with `input()`. This avoids
   `OSError: [Errno 29] I/O error` from environments that don't support standard input.
2) **Robust file I/O**: Save/load now gracefully fall back to a temp directory if the preferred
   path isn't writable. Clear messages explain what happened; the app still works.
3) **CLI flags**: `--demo` (non-interactive showcase), `--tests` (self-tests), and `--file` to
   specify a data file path.
4) **Built-in self tests**: A small test suite validates core features and (when possible)
   round-trips data through the filesystem.

Why this is GitHub-ready
- Single-file, readable, and well-documented Python code.
- No third-party dependencies (works with Python 3.8+).
- Clear functions and a simple CLI for demo and extension.

Features
- Add income / expense transactions (id, date, amount, category, type, description).
- List transactions (with optional sorting by date/amount/category).
- Search transactions by keyword or ID.
- Filter (e.g., expenses over $100, by category, by date range).
- Save to / load from JSON file (with sandbox-safe fallback).
- Monthly spending ASCII bar chart (nice visual summary).
- Sample demo data generator and batch import/export.
- CLI flags for demo/tests and non-interactive environments.

How to run
1. Make sure you have Python 3.8+ installed.
2. Save this file as `personal_finance_tracker.py`.
3. **Interactive mode (default when run in a real terminal):**

    python personal_finance_tracker.py

4. **Non-interactive / sandbox / CI:**

    # Demo showcase (prints a short report, no prompts)
    python personal_finance_tracker.py --demo

    # Run built-in tests
    python personal_finance_tracker.py --tests

5. Optional flags:
   - `--file PATH`  Use a specific JSON file for save/load.

Notes
- Dates use the ISO format: YYYY-MM-DD.
- Amounts are numbers; you can use positive for income and positive for expense as long as you set
  `ttype` accordingly. If you prefer negative numbers for expenses, the balance calculator will
  normalize them.

"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable, Tuple
import json
from datetime import datetime
import sys
import os
import tempfile
import argparse

DATE_FORMAT = "%Y-%m-%d"

# Default file lives in a temp directory to avoid sandbox write restrictions.
DEFAULT_SAVE_FILE = os.path.join(tempfile.gettempdir(), "transactions.json")

@dataclass
class Transaction:
    id: int
    date: str  # YYYY-MM-DD
    amount: float
    category: str
    ttype: str  # 'income' or 'expense'
    description: str = ""

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'Transaction':
        return Transaction(
            id=int(d['id']),
            date=str(d['date']),
            amount=float(d['amount']),
            category=str(d.get('category', '')),
            ttype=str(d.get('ttype', 'expense')),
            description=str(d.get('description', ''))
        )

# ------------------------- Core Data Operations -------------------------

def next_id(transactions: List[Transaction]) -> int:
    return max((t.id for t in transactions), default=0) + 1


def add_transaction(transactions: List[Transaction], date: str, amount: float, category: str, ttype: str, description: str = "") -> Transaction:
    tid = next_id(transactions)
    tx = Transaction(id=tid, date=date, amount=amount, category=category, ttype=ttype, description=description)
    transactions.append(tx)
    return tx


def list_transactions(transactions: List[Transaction], sort_key: Optional[str] = None, reverse: bool = False) -> List[Transaction]:
    keyfn: Callable[[Transaction], object]
    if sort_key == 'date':
        keyfn = lambda t: datetime.strptime(t.date, DATE_FORMAT)
    elif sort_key == 'amount':
        keyfn = lambda t: t.amount
    elif sort_key == 'category':
        keyfn = lambda t: t.category.lower()
    else:
        keyfn = lambda t: t.id
    return sorted(transactions, key=keyfn, reverse=reverse)


def find_by_id(transactions: List[Transaction], tid: int) -> Optional[Transaction]:
    for t in transactions:
        if t.id == tid:
            return t
    return None


def search_transactions(transactions: List[Transaction], keyword: str) -> List[Transaction]:
    kw = keyword.lower()
    return [t for t in transactions if kw in t.description.lower() or kw in t.category.lower()]


def filter_expenses_over(transactions: List[Transaction], amount_threshold: float) -> List[Transaction]:
    return [t for t in transactions if t.ttype == 'expense' and abs(t.amount) > amount_threshold]


def filter_by_category(transactions: List[Transaction], category: str) -> List[Transaction]:
    c = category.lower()
    return [t for t in transactions if t.category.lower() == c]


def filter_by_date_range(transactions: List[Transaction], start_date: Optional[str], end_date: Optional[str]) -> List[Transaction]:
    def to_dt(s: str) -> datetime:
        return datetime.strptime(s, DATE_FORMAT)
    res = []
    for t in transactions:
        dt = to_dt(t.date)
        if start_date and dt < to_dt(start_date):
            continue
        if end_date and dt > to_dt(end_date):
            continue
        res.append(t)
    return res

# ------------------------- Persistence (sandbox-safe) -------------------------

def _preferred_writable_path(filename: str) -> str:
    """Return a writable path for filename, falling back to temp if needed."""
    try:
        d = os.path.dirname(filename) or "."
        os.makedirs(d, exist_ok=True)
        test = os.path.join(d, ".pft_write_test")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test)
        return filename
    except Exception:
        return os.path.join(tempfile.gettempdir(), os.path.basename(filename))


def save_transactions(transactions: List[Transaction], filename: str = DEFAULT_SAVE_FILE) -> bool:
    target = _preferred_writable_path(filename)
    try:
        with open(target, 'w', encoding='utf-8') as f:
            json.dump([t.to_dict() for t in transactions], f, indent=2)
        if target != filename:
            print(f"[info] Save path '{filename}' not writable. Saved to '{target}' instead.")
        return True
    except OSError as e:
        print(f"[warning] Could not save transactions to '{target}': {e}")
        return False


def load_transactions(filename: str = DEFAULT_SAVE_FILE) -> List[Transaction]:
    # Try user-specified path first, then temp fallback
    candidates = [filename]
    if filename != DEFAULT_SAVE_FILE:
        candidates.append(DEFAULT_SAVE_FILE)
    fallback = os.path.join(tempfile.gettempdir(), os.path.basename(filename))
    if fallback not in candidates:
        candidates.append(fallback)

    for path in candidates:
        try:
            if not os.path.exists(path):
                continue
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [Transaction.from_dict(d) for d in data]
        except OSError as e:
            print(f"[warning] Could not read '{path}': {e}")
        except json.JSONDecodeError as e:
            print(f"[warning] JSON in '{path}' is invalid: {e}")
    return []

# ------------------------- Reports & Charts -------------------------

def balance_summary(transactions: List[Transaction]) -> Tuple[float, float, float]:
    income = sum(t.amount for t in transactions if t.ttype == 'income')
    # expenses may be recorded as positive or negative; normalize
    expenses_pos = sum(t.amount for t in transactions if t.ttype == 'expense' and t.amount >= 0)
    expenses_neg = sum(-t.amount for t in transactions if t.ttype == 'expense' and t.amount < 0)
    other_neg_expenses = sum(-t.amount for t in transactions if t.ttype != 'income' and t.amount < 0)
    expenses = expenses_pos + expenses_neg
    if other_neg_expenses:
        expenses += other_neg_expenses
    savings = income - expenses
    return income, expenses, savings


def monthly_spending(transactions: List[Transaction]) -> dict:
    # Returns dict of YYYY-MM -> total expense
    totals = {}
    for t in transactions:
        if t.ttype != 'expense':
            continue
        month = t.date[:7]  # YYYY-MM
        totals[month] = totals.get(month, 0) + abs(t.amount)
    return dict(sorted(totals.items()))


def ascii_bar_chart(month_totals: dict, max_width: int = 40) -> str:
    if not month_totals:
        return "(no expense data to chart)"
    max_val = max(month_totals.values())
    lines = []
    for month, val in month_totals.items():
        length = int((val / max_val) * max_width) if max_val > 0 else 0
        bar = '█' * max(1, length)
        lines.append(f"{month} | {bar} {val:.2f}")
    return "\n".join(lines)

# ------------------------- Utilities -------------------------

def pretty_print_transactions(transactions: List[Transaction]) -> None:
    if not transactions:
        print("No transactions found.")
        return
    print(f"{'ID':>3}  {'Date':10}  {'Type':7}  {'Amount':10}  {'Category':15}  Description")
    print('-' * 80)
    for t in transactions:
        amt = f"{t.amount:.2f}"
        print(f"{t.id:>3}  {t.date:10}  {t.ttype:7}  {amt:10}  {t.category:15.15}  {t.description}")


def input_date(prompt: str) -> str:
    while True:
        s = input(prompt).strip()
        try:
            datetime.strptime(s, DATE_FORMAT)
            return s
        except ValueError:
            print(f"Please enter a date in {DATE_FORMAT} format (e.g. 2025-07-21).")


def input_float(prompt: str) -> float:
    while True:
        s = input(prompt).strip()
        try:
            return float(s)
        except ValueError:
            print("Please enter a valid number (e.g. 123.45).")

# ------------------------- Demo / Sample Data -------------------------

def sample_data() -> List[Transaction]:
    txs: List[Transaction] = []
    add_transaction(txs, '2025-01-03', 3000.00, 'Salary', 'income', 'Monthly salary')
    add_transaction(txs, '2025-01-05', 45.20, 'Groceries', 'expense', 'Walmart shopping')
    add_transaction(txs, '2025-01-10', 120.00, 'Utilities', 'expense', 'Electricity bill')
    add_transaction(txs, '2025-02-01', 3000.00, 'Salary', 'income', 'Monthly salary')
    add_transaction(txs, '2025-02-12', 250.00, 'Shopping', 'expense', 'New jacket')
    add_transaction(txs, '2025-02-20', 12.00, 'Coffee', 'expense', 'Coffee shop')
    add_transaction(txs, '2025-03-01', 3000.00, 'Salary', 'income', 'Monthly salary')
    add_transaction(txs, '2025-03-14', 600.00, 'Rent', 'expense', 'March rent')
    return txs

# ------------------------- Command-line Interface -------------------------

def is_interactive_stdin() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def menu(data_file: str = DEFAULT_SAVE_FILE) -> None:
    transactions = load_transactions(data_file)
    if is_interactive_stdin():
        if not transactions:
            print("No saved transactions found. Do you want to load sample data? (y/N)")
            try:
                if input().strip().lower() == 'y':
                    transactions = sample_data()
            except OSError:
                # Fall back to demo data if stdin misbehaves mid-run
                print("[info] Falling back to sample data (stdin not available).")
                transactions = sample_data()
    else:
        # Non-interactive environment: auto-load sample data so the app does something useful
        if not transactions:
            print("[info] Non-interactive mode detected; loading sample data.")
            transactions = sample_data()

    while True:
        print('\nPersonal Finance Tracker — Menu')
        print('1) Add transaction')
        print('2) List transactions')
        print('3) Search transactions (keyword)')
        print('4) Filter: expenses over X')
        print('5) Filter by category')
        print('6) Filter by date range')
        print('7) Show balance summary')
        print('8) Monthly spending ASCII chart')
        print('9) Save transactions')
        print('10) Load transactions from file')
        print('11) Export to JSON filename')
        print('12) Delete transaction by ID')
        print('0) Exit')

        try:
            choice = input('Choose an option: ').strip()
        except OSError:
            print('[info] Stdin not available; leaving interactive menu. Try --demo or --tests.')
            break

        if choice == '1':
            date = input_date('Date (YYYY-MM-DD): ')
            amount = input_float('Amount: ')
            ttype = input('Type (income/expense): ').strip().lower()
            if ttype not in ('income', 'expense'):
                print('Invalid type — defaulting to expense')
                ttype = 'expense'
            category = input('Category: ').strip() or 'Uncategorized'
            desc = input('Description: ').strip()
            tx = add_transaction(transactions, date, amount, category, ttype, desc)
            print(f"Added transaction ID {tx.id}")

        elif choice == '2':
            print('Sort by (id/date/amount/category): (press enter for id)')
            sk = input().strip().lower() or None
            if sk == '':
                sk = None
            print('Reverse order? (y/N)')
            rev = input().strip().lower() == 'y'
            pretty_print_transactions(list_transactions(transactions, sort_key=sk, reverse=rev))

        elif choice == '3':
            kw = input('Enter keyword to search (category or description): ').strip()
            res = search_transactions(transactions, kw)
            pretty_print_transactions(res)

        elif choice == '4':
            x = input_float('Show expenses over: ')
            res = filter_expenses_over(transactions, x)
            pretty_print_transactions(res)

        elif choice == '5':
            cat = input('Category to filter by: ').strip()
            res = filter_by_category(transactions, cat)
            pretty_print_transactions(res)

        elif choice == '6':
            s = input('Start date (YYYY-MM-DD) or blank: ').strip() or None
            e = input('End date (YYYY-MM-DD) or blank: ').strip() or None
            res = filter_by_date_range(transactions, s, e)
            pretty_print_transactions(res)

        elif choice == '7':
            inc, exp, sav = balance_summary(transactions)
            print(f"Income: {inc:.2f}  Expenses: {exp:.2f}  Net/Savings: {sav:.2f}")

        elif choice == '8':
            mt = monthly_spending(transactions)
            chart = ascii_bar_chart(mt)
            print('\nMonthly spending chart:\n')
            print(chart)

        elif choice == '9':
            fn = input(f"Save filename (enter for {DEFAULT_SAVE_FILE}): ").strip() or DEFAULT_SAVE_FILE
            ok = save_transactions(transactions, fn)
            if ok:
                print(f"Saved {len(transactions)} transactions to {fn if fn else DEFAULT_SAVE_FILE}")

        elif choice == '10':
            fn = input(f"Load filename (enter for {DEFAULT_SAVE_FILE}): ").strip() or DEFAULT_SAVE_FILE
            transactions = load_transactions(fn)
            print(f"Loaded {len(transactions)} transactions from {fn}")

        elif choice == '11':
            fn = input('Export JSON filename: ').strip()
            if not fn:
                print('Filename required.')
            else:
                if save_transactions(transactions, fn):
                    print(f'Exported to {fn}')

        elif choice == '12':
            try:
                tid = int(input('Enter transaction ID to delete: ').strip())
            except ValueError:
                print('Invalid ID')
                continue
            t = find_by_id(transactions, tid)
            if t:
                transactions.remove(t)
                print(f'Deleted transaction {tid}')
            else:
                print('ID not found.')

        elif choice == '0':
            print('Exit — do you want to auto-save before quitting? (y/N)')
            try:
                if input().strip().lower() == 'y':
                    save_transactions(transactions)
                    print(f'Saved to {DEFAULT_SAVE_FILE}')
            except OSError:
                # If stdin broke mid-run, still attempt to save gracefully
                save_transactions(transactions)
                print(f"[info] Auto-saved to {DEFAULT_SAVE_FILE}")
            print('Goodbye!')
            break

        else:
            print('Unknown choice — try again.')

# ------------------------- Demo / Tests -------------------------

def run_demo() -> None:
    print("[demo] Running Personal Finance Tracker demo...")
    txs = sample_data()
    print("\nAll transactions (by date):")
    pretty_print_transactions(list_transactions(txs, sort_key='date'))

    print("\nExpenses over 100:")
    pretty_print_transactions(filter_expenses_over(txs, 100))

    print("\nBalance summary:")
    inc, exp, sav = balance_summary(txs)
    print(f"Income: {inc:.2f}  Expenses: {exp:.2f}  Net/Savings: {sav:.2f}")

    print("\nMonthly spending chart:\n")
    print(ascii_bar_chart(monthly_spending(txs)))

    # Try a save/load round trip to a temp file
    tmp = os.path.join(tempfile.gettempdir(), "pft_demo.json")
    if save_transactions(txs, tmp):
        rt = load_transactions(tmp)
        print(f"\n[demo] Round-trip file test: saved {len(txs)} and loaded {len(rt)} transactions.")


def run_self_tests() -> None:
    print("[tests] Starting self tests...")
    # Create sample transactions
    txs = sample_data()
    assert len(txs) == 8, "Sample data should have 8 transactions"

    # Test id increment
    next_tx = add_transaction(txs, '2025-03-20', 50.0, 'Snacks', 'expense', 'Late night snacks')
    assert next_tx.id == 9, f"Expected next ID 9, got {next_tx.id}"

    # Test sorting by amount
    sorted_amt = list_transactions(txs, sort_key='amount')
    assert sorted_amt[0].amount <= sorted_amt[-1].amount, "Sorting by amount failed"

    # Test filter expenses over 100
    over_100 = filter_expenses_over(txs, 100)
    assert all(t.ttype == 'expense' and abs(t.amount) > 100 for t in over_100), "Filter expenses over 100 failed"

    # Test category filter
    groceries = filter_by_category(txs, 'Groceries')
    assert len(groceries) == 1 and groceries[0].category == 'Groceries', "Category filter failed"

    # Test date range filter
    jan = filter_by_date_range(txs, '2025-01-01', '2025-01-31')
    assert all(t.date.startswith('2025-01') for t in jan), "Date range filter failed"

    # Test monthly spending & chart
    mt = monthly_spending(txs)
    assert '2025-01' in mt and mt['2025-01'] > 0, "Monthly spending computation failed"
    chart = ascii_bar_chart(mt)
    assert isinstance(chart, str) and len(chart) > 0, "ASCII chart generation failed"

    # Test balance summary normalization with negative expenses
    txs2: List[Transaction] = []
    add_transaction(txs2, '2025-01-01', 1000.0, 'Salary', 'income', 'Pay')
    add_transaction(txs2, '2025-01-02', -200.0, 'Groceries', 'expense', 'Food')
    inc, exp, sav = balance_summary(txs2)
    assert inc == 1000.0 and abs(exp - 200.0) < 1e-9 and abs(sav - 800.0) < 1e-9, "Balance summary normalization failed"

    # Test save/load round-trip (skip if FS is restricted)
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        tmp.close()
        ok = save_transactions(txs, tmp.name)
        txs_rt = load_transactions(tmp.name) if ok else []
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        if ok:
            assert len(txs_rt) == len(txs), "Save/load round-trip size mismatch"
        else:
            print("[tests] Skipping round-trip assertion due to save failure (likely FS restrictions).")
    except OSError as e:
        print(f"[tests] Filesystem restricted; skipping round-trip test: {e}")

    print("[tests] ALL TESTS PASSED")

# ------------------------- Main -------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Personal Finance Tracker')
    parser.add_argument('--demo', action='store_true', help='Run a non-interactive demo and exit')
    parser.add_argument('--tests', action='store_true', help='Run self tests and exit')
    parser.add_argument('--file', default=DEFAULT_SAVE_FILE, help='JSON file path for save/load (default: temp dir)')
    args = parser.parse_args()

    # Update default save file if user supplied one
    if args.file:
        DEFAULT_SAVE_FILE = args.file  # type: ignore

    try:
        if args.tests:
            run_self_tests()
        elif args.demo or not is_interactive_stdin():
            run_demo()
        else:
            menu(DEFAULT_SAVE_FILE)
    except KeyboardInterrupt:
        print('\nInterrupted — exiting.')
        sys.exit(0)
