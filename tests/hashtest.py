import bcrypt
pw = b"Likliklik"
s = bcrypt.gensalt()
h = bcrypt.hashpw(pw, s)
entered_pw = b"Likliklik"

if bcrypt.checkpw(entered_pw, h):
    print("Password match!")
else:
    print("Incorrect password")