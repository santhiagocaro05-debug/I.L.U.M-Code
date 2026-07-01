
import tkinter as tk

root = tk.Tk()
root.title("ILUM Hologram")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.8)
root.attributes("-transparentcolor", "black")

# Dimensiones y posición
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
w = 800
h = 100
x = (screen_width/2) - (w/2)
y = screen_height - 150
root.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
root.configure(bg="black")

label = tk.Label(root, text="Traductor Holográfico Iniciado", font=("Helvetica", 24, "bold"), fg="#00FFFF", bg="black")
label.pack(expand=True, fill="both")

# Autocerrar después de unos segundos
root.after(5000, root.destroy)
root.mainloop()
