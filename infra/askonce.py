"""
A yes/no question the deploy asks once per machine. The answer is kept in a
file, so later deploys read it instead of asking. Delete the file to be asked
again on the next deploy.

    python3 -I infra/askonce.py   # self-check
"""
import pathlib


def ask_once(path, question, tty="/dev/tty"):
    """With no tty, opening it raises, so the deploy fails and chezmoi runs it
    again on the next apply.
    """
    path = pathlib.Path(path).expanduser()
    if path.exists():
        return path.read_text().strip()
    # Unbuffered binary: a tty is not seekable, which text-mode r+ requires.
    with open(tty, "r+b", buffering=0) as t:
        t.write(f"{question} [y/N] ".encode())
        answer = "yes" if t.readline().strip().lower() in (b"y", b"yes") else "no"
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
    print("askonce OK")
