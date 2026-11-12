import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from interface_viviane import VivianeApp

if __name__ == '__main__':
    app = VivianeApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.parar()
