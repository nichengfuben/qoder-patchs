from sc.cli import main
from sc.encoding import ensure_utf8_stdio

if __name__ == "__main__":
    ensure_utf8_stdio()
    raise SystemExit(main())
