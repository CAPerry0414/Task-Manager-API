from flask import Flask, request
from database import db
import bcrypt
import jwt

app = Flask(__name__)

db_name = "task_manager.db"

# Configuring SQLite Database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_name

# Suppresses warning while tracking modifications
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure the secret key
app.config['JWT_SECRET_KEY'] = "super-secret-value-123"

# Initialising SQLAlchemy with Flask App
db.init_app(app)

""" Creating Database with App Context"""
def create_db():
    with app.app_context():
        from models import User
        from models import Task
        db.create_all()

# Authentication function
def authenticate():
    if "Authorization" not in request.headers:
        return None

    auth_header = request.headers["Authorization"]

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:len(auth_header)]
    try:
        decoded = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms="HS256")
    except jwt.PyJWTError:
        return None

    return decoded["sub"]

@app.route("/")
def task_manager():
    return "<p>Task manager API is running!</p>"


@app.route("/signup", methods=["POST"])
def signup():
    # Retrieve the user data from the request body
    new_user = request.get_json()
    # Check for inputs
    if not new_user or "username" not in new_user or "password" not in new_user:
        return "Error: Username or password not entered", 400

    if new_user["username"] == "" or new_user["password"] == "":
        return "Error: Username or password not entered", 400

    if not isinstance(new_user["username"], str) or not isinstance(new_user["password"], str):
        return "Error: Username or password data type is incorrect", 400

    from models import User
    user = db.session.execute(db.select(User).filter_by(username=new_user["username"])).scalar()
    if user:
        return "A user with this username already exists. Please choose another.", 400

    # Hash the password
    s = bcrypt.gensalt()
    h = bcrypt.hashpw((new_user["password"]).encode("utf-8"), s)

    # Create the new object 
    add_user = User(
        username=new_user["username"],
        password_hash=h
    )

    # Adding the user to the SQLAlchemy session
    db.session.add(add_user)
    db.session.commit()
    return "User successfully added", 201


@app.route("/login", methods=["POST"])
def login():
    # Retrieve the user data from the request body
    user = request.get_json()
    if not user or "username" not in user or "password" not in user:
        return "Error: Username or password not entered", 400

    if not isinstance(user["username"], str) or not isinstance(user["password"], str):
        return "Error: Username or password data type is incorrect", 400

    # Find the username in the database
    from models import User
    search_user = db.session.execute(db.select(User).filter_by(username=user["username"])).scalar()

    if not search_user:
        return "Username not found. Please try again.", 400

    # Verify the password
    su_ph = search_user.password_hash
    if not bcrypt.checkpw(user["password"].encode("utf-8"), su_ph):
        return "Error: Incorrect password", 400

    # Encode the user id
    encoded = jwt.encode({"sub" : str(search_user.user_id)}, app.config["JWT_SECRET_KEY"], algorithm="HS256")

    # Return a JSON object to the API client
    return {"token" : encoded}, 200


@app.route("/tasks", methods=["POST"])
def create_task():
    # Authenticate the user
    user_id = authenticate() 
    if user_id is None:
        return "Unauthorized", 401

    # Retrieve the task
    task = request.get_json()

    if not task or "title" not in task or "description" not in task or "status" not in task:
        return "Invalid task", 400

    if task["title"] == "" or task["description"] == "" or task["status"] == "":
        return "Invalid task", 400

    if not isinstance(task["title"], str) or not isinstance(task["description"], str) or not isinstance(task["status"], str):
        return "Invalid task", 400

    if "category" not in task or not isinstance(task["category"], str):
        task["category"] = None

    from models import Task
    add_task = Task(
        title=task["title"],
        description=task["description"],
        category=task["category"],
        status=task["status"],
        user_id=user_id
    )

    db.session.add(add_task)
    db.session.commit()


    return {
        "task_id": add_task.task_id,
        "title": add_task.title,
        "description": add_task.description,
        "category": add_task.category,
        "status": add_task.status,
        "user_id": add_task.user_id,
    }, 201

@app.route("/tasks", methods=["GET"])
def retrieve_tasks():
    # Authenticate the user
    user_id = authenticate()
    if user_id is None:
        return "Unauthorized", 401

    # Query the task table and retrieve all tasks associated with the user
    from models import Task
    stmt = db.select(Task).filter_by(user_id=user_id)

    # Add optional arguments
    if "status" in request.args:
        status = request.args["status"]
        stmt = stmt.where(Task.status == status)

    if "category" in request.args:
        category = request.args["category"]
        stmt = stmt.where(Task.category == category)

    tasks = db.session.scalars(stmt)

    # Create a list of tasks converted to JSON and return it
    task_list = []
    

    for task in tasks:
        task_list.append({
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "category": task.category,
            "status": task.status,
            "user_id": user_id
        })

    return task_list, 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def retrieve_task(task_id):
    # Authenticate the user
    user_id = authenticate()
    if user_id is None:
        return "Unauthorized", 401

    # Retrieve the task with the task id
    from models import Task
    stmt = db.select(Task).where(Task.task_id == task_id, Task.user_id == user_id)
    task = db.session.scalars(stmt).first()

    if not task:
        return "Task not found", 404

    # Return the task
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "category": task.category,
        "status": task.status,
        "user_id": user_id
    }, 200


@app.route("/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    # Authenticate the user
    user_id = authenticate()
    if user_id is None:
        return "Unauthorized", 401

    # Retrieve the task with the task id
    from models import Task
    stmt = db.select(Task).where(Task.task_id == task_id, Task.user_id == user_id)
    task = db.session.scalars(stmt).first()

    if not task:
        return "Task not found", 404

    # Update the task
    updated_attributes = request.get_json()

    if not isinstance(updated_attributes, dict):
        return "Invalid request", 400

    if updated_attributes == None or updated_attributes == {}:
        return "No fields provided to update", 400

    allowed = {"category", "title", "description", "status"}

    # Validity check
    for (key, value) in updated_attributes.items():
        if key in allowed:
            if key == "title" or key == "description" or key == "status":
                if value == "" or not isinstance(value, str):
                    return "Request body invalid", 400

            if key == "category" and not isinstance(value, str) and value is not None:
                return "Bad request", 400
        else:
            return "Bad request", 400
        
    # Update the attribute
    for (key, value) in updated_attributes.items():
        setattr(task, key, value)

    db.session.commit()

    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "category": task.category,
        "status": task.status,
        "user_id": user_id
    }, 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id): 
    # Authenticate the user
    user_id = authenticate()
    if user_id is None:
        return "Unauthorized", 401

    # Retrieve the task with the task id
    from models import Task
    stmt = db.select(Task).where(Task.task_id == task_id, Task.user_id == user_id)
    task = db.session.scalars(stmt).first()

    if not task:
        return "Task not found", 404

    # Delete the task
    db.session.delete(task)
    db.session.commit()

    return "", 204


if __name__ == "__main__":
    create_db()
    app.run(debug=True)
