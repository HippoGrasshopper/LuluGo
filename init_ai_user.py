from sqlmodel import Session, select
from database import User, engine

def ensure_ai_user():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "KataGo")).first()
        if not user:
            print("[Init] Creating AI User 'KataGo'")
            user = User(username="KataGo")
            session.add(user)
            session.commit()
        else:
            print(f"[Init] AI User 'KataGo' exists (ID: {user.id})")

if __name__ == "__main__":
    ensure_ai_user()
