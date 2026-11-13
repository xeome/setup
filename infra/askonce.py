"""
A question the deploy asks once per machine: yes or no, or a line of text.
The answer is kept in a file, so later deploys read it instead of asking.
Delete the file to be asked again on the next deploy.

    python3 -I infra/askonce.py   # self-check
"""
import pathlib


def ask_once(path, question, tty="/dev/tty", text=False):
    """With no tty, opening it raises, so the deploy fails and the next apply
    asks again. So does an empty line where text is wanted.
    """
    path = pathlib.Path(path).expanduser()
    if path.exists():
        return path.read_text().strip()
    # Unbuffered binary: a tty is not seekable, which text-mode r+ requires.
    with open(tty, "r+b", buffering=0) as t:
        t.write(f"{question} ".encode() if text else f"{question} [y/N] ".encode())
        line = t.readline().decode().strip()
    if text and not line:
        raise ValueError(f"no answer to: {question}")
    answer = line if text else "yes" if line.lower() in ("y", "yes") else "no"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(answer)
    return answer


if __name__ == "__main__":
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HOME"] = tmp
        missing = f"{tmp}/no-such-tty"

        cached = pathlib.Path(tmp, "cached")
        cached.write_text("no")
        assert ask_once(cached, "q?", tty=missing) == "no"

        for typed, want in ((b"y\n", "yes"), (b"\n", "no")):
            master, slave = os.openpty()
            os.write(master, typed)
            answer = f"~/{want}/b/answer"
            got = ask_once(answer, "Transcribe voice notes?", tty=os.ttyname(slave))
            prompt = os.read(master, 4096)
            os.close(master)
            os.close(slave)
            assert got == want, f"typed {typed!r}, got {got!r}"
            assert b"Transcribe voice notes?" in prompt, prompt
            kept = pathlib.Path(tmp, want, "b/answer")
            assert kept.read_text() == want, f"{kept} holds {kept.read_text() if kept.exists() else 'nothing'!r}"
            assert ask_once(answer, "q?", tty=missing) == want, "a cached answer was not reused"

        try:
            ask_once("~/fresh/answer", "q?", tty=missing)
        except OSError:
            pass
        else:
            raise AssertionError("ask_once returned with no tty")
        assert not pathlib.Path(tmp, "fresh/answer").exists()

        for typed, want in (("Ada O'Löve\n", "Ada O'Löve"), ("\n", None)):
            master, slave = os.openpty()
            os.write(master, typed.encode())
            try:
                got = ask_once("~/text/name", "Your name for git commits?", tty=os.ttyname(slave), text=True)
            except ValueError:
                got = None
            prompt = os.read(master, 4096)
            os.close(master)
            os.close(slave)
            assert got == want, f"typed {typed!r}, got {got!r}"
            assert b"[y/N]" not in prompt, prompt
            assert pathlib.Path(tmp, "text/name").exists() == bool(want)
            pathlib.Path(tmp, "text/name").unlink(missing_ok=True)
    print("askonce OK")
