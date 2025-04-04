import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
import winsound
import threading
import nfc
import time
from fpdf import FPDF

# ==================================
# Author: Leonard Hauschild
# Date: 26.03.2025
# Description: This program was created, designed, documented, and tested by Leonard Hauschild.
# It is an inventory management software with functions such as viewing stock, searching for materials, saving reports, and tracking withdrawals/returns.
# Technologies used: Python, TKinter, MySQL, NFC, FPDF
#
# This software is copyrighted. Unauthorized reproduction or distribution of the code is prohibited.
# ==================================

# Establish connection to the database
def connect_to_db():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="inventory_db"
        )
        if connection.is_connected():
            return connection
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Error connecting to the database: {err}")
        return None

# Display inventory
def view_inventory():
    connection = connect_to_db()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT material_id, name, category, quantity, length, shelf_location, shelf_height, min_quantity, color FROM material")
        inventory = cursor.fetchall()

        for row in tree.get_children():
            tree.delete(row)
        
        for item in inventory:
            # Fetch min_quantity and color for each material from the database
            min_quantity = item[7]  # Min quantity is in the 8th column (index 7)
            color = item[8]  # Color is in the 9th column (index 8)
            
            # Check if stock is below minimum quantity and adjust color accordingly
            tree.insert("", "end", values=(item[0], item[1], item[2], item[3], item[4], item[5], item[6], item[8]), 
            tags=("low_stock" if item[3] < min_quantity else "normal"))

        cursor.close()
        connection.close()

# Search function
def search_inventory():
    search_term = search_entry.get().strip()
    search_column = search_option.get()
    column_map = {"Name": "name", "Category": "category", "Length": "length", "Color": "color"}
    
    if not search_term:
        messagebox.showerror("Error", "Please enter a search term.")
        return
    
    connection = connect_to_db()
    if connection:
        cursor = connection.cursor()
        query = f"SELECT material_id, name, category, quantity, length, shelf_location, shelf_height, color FROM material WHERE {column_map[search_column]} LIKE %s"
        cursor.execute(query, (f"%{search_term}%",))
        results = cursor.fetchall()

        for row in tree.get_children():
            tree.delete(row)
        
        if results:
            for row in results:
                tree.insert("", "end", values=row)
        else:
            messagebox.showinfo("Info", "No results found.")
        
        cursor.close()
        connection.close()

# Save report (TXT or PDF)
def save_report():
    filetypes = [("Text file", "*.txt"), ("PDF file", "*.pdf")]
    file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=filetypes)

    if not file_path:
        return
    
    connection = connect_to_db()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM material")
        data = cursor.fetchall()

        if file_path.endswith(".txt"):
            with open(file_path, "w") as f:
                for row in data:
                    f.write(", ".join(str(item) for item in row) + "\n")
        else:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for row in data:
                pdf.cell(200, 10, txt=", ".join(str(item) for item in row), ln=True)
            pdf.output(file_path)

        cursor.close()
        connection.close()
        messagebox.showinfo("Success", f"Report saved at {file_path}")

# Automatically handle withdrawals and returns
def handle_inventory():
    global last_scan_time
    last_scan_time = time.time()
    user_tag = nfc_user_label.cget("text")
    material_tag = nfc_material_label.cget("text")
    
    # If no tag has been scanned yet, do nothing
    if user_tag == "Not scanned" or material_tag == "Not scanned":
        return

    if time.time() - last_scan_time > 30:
        quantity = int(quantity_entry.get()) if checkbox_var.get() else 1
        connection = connect_to_db()
        if connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT quantity FROM material WHERE material_id = {material_tag}")
            material = cursor.fetchone()
            
            if material and material[0] >= quantity:
                new_quantity = material[0] - quantity
                cursor.execute(f"UPDATE material SET quantity = {new_quantity} WHERE material_id = {material_tag}")
                cursor.execute(f"INSERT INTO inventory_log (user_tag, material_tag, quantity, action) VALUES ('{user_tag}', '{material_tag}', {quantity}, 'Withdrawal')")
                connection.commit()
                messagebox.showinfo("Success", f"{quantity} units of {material_tag} withdrawn.")
            else:
                messagebox.showerror("Error", "Not enough material available.")
            
            cursor.close()
            connection.close()

# Function for continuous NFC scanning
def scan_nfc(label):
    try:
        clf = nfc.ContactlessFrontend('usb')
        tag = clf.connect(rdwr={'on-connect': lambda tag: False})
        label.config(text=f"Scanned NFC Tag: {tag.identifier}", fg="green")
        winsound.Beep(1000, 200)
    except Exception:
        label.config(text="No tag detected", fg="red")

# Thread for continuous NFC scanning
def constant_nfc_scan():
    while True:
        scan_nfc(nfc_user_label)
        scan_nfc(nfc_material_label)

# GUI Setup
root = tk.Tk()
root.title("Inventory Management")

frame_controls = tk.Frame(root)
frame_controls.pack(pady=10)

btn_view_inventory = tk.Button(frame_controls, text="View Inventory", command=view_inventory)
btn_view_inventory.grid(row=0, column=0, padx=5)

search_option = tk.StringVar(value="Name")
search_dropdown = ttk.Combobox(frame_controls, textvariable=search_option, values=("Name", "Category", "Length", "Color"))
search_dropdown.grid(row=0, column=1, padx=5)

search_entry = tk.Entry(frame_controls, width=30)
search_entry.grid(row=0, column=2, padx=5)

btn_search = tk.Button(frame_controls, text="Search", command=search_inventory)
btn_search.grid(row=0, column=3, padx=5)

tree = ttk.Treeview(root, columns=("ID", "Name", "Category", "Quantity", "Length", "Shelf", "Height", "Color"), show="headings")
for col in ("ID", "Name", "Category", "Quantity", "Length", "Shelf", "Height", "Color"):
    tree.heading(col, text=col)
    tree.column(col, width=100)
tree.pack(pady=10)

tree.tag_configure("low_stock", background="red")
tree.tag_configure("normal", background="white")

btn_scan_user = tk.Button(root, text="Scan User NFC", command=lambda: scan_nfc(nfc_user_label))
btn_scan_user.pack(pady=5)
nfc_user_label = tk.Label(root, text="User NFC: Not scanned", fg="black")
nfc_user_label.pack()

btn_scan_material = tk.Button(root, text="Scan Material NFC", command=lambda: scan_nfc(nfc_material_label))
btn_scan_material.pack(pady=5)
nfc_material_label = tk.Label(root, text="Material NFC: Not scanned", fg="black")
nfc_material_label.pack()

btn_save_report = tk.Button(root, text="Save Report", command=save_report)
btn_save_report.pack(pady=5)

threading.Thread(target=constant_nfc_scan, daemon=True).start()

root.mainloop()
