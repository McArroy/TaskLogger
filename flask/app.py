import os
import secrets
from datetime import datetime
from flask import flash
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_bcrypt import Bcrypt
from flask_login import current_user
from flask_login import LoginManager
from flask_login import login_required
from flask_login import login_user
from flask_login import logout_user
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import PasswordField
from wtforms import StringField
from wtforms import SubmitField
from wtforms.validators import DataRequired
from wtforms.validators import EqualTo
from wtforms.validators import Length
from wtforms.validators import ValidationError

app = Flask(__name__)

# Database
database_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "databases")
os.makedirs(database_dir, exist_ok = True)

app.config["SECRET_KEY"] = secrets.token_hex(16)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(database_dir, 'tasklogger.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def user_loader(user_id):
	return User.query.get(int(user_id))

class User(UserMixin, db.Model):
	id = db.Column(db.Integer, primary_key = True)
	username = db.Column(db.String(40), unique = True, nullable = False)
	password_hash = db.Column(db.String(128), nullable = False)
	tasks = db.relationship("AddTask", backref = "user", lazy = True)

	@property
	def password(self):
		return self.password
	
	@password.setter
	def password(self, plain_text_password):
		self.password_hash = bcrypt.generate_password_hash(plain_text_password).decode("utf-8")

	def check_password_correction(self, attempted_password):
		return bcrypt.check_password_hash(self.password_hash, attempted_password)

class RegisterForm(FlaskForm):
	def validate_username(self, username_to_check):
		user = User.query.filter_by(username = username_to_check.data).first()
		if (user):
			raise ValidationError("Username is already exists! Please try a different username")

	username = StringField(validators = [Length(min = 2, max = 40), DataRequired()], render_kw = {"placeholder": "Enter your username", "title": "Enter your username"})
	password1 = PasswordField(validators = [Length(min = 8, max = 128), DataRequired()], render_kw = {"placeholder": "Enter your password", "title": "Enter your password"})
	password2 = PasswordField(validators = [EqualTo("password1"), DataRequired()], render_kw = {"placeholder": "Confirm your password", "title": "Confirm your password"})
	submit = SubmitField(label = "Create Account", render_kw = {"title": "Create and Sign in now"})

class LoginForm(FlaskForm):
	username = StringField(validators = [Length(min = 2, max = 40), DataRequired()], render_kw = {"placeholder": "Enter your username", "title": "Enter your username"})
	password = PasswordField(validators = [Length(min = 8, max = 128), DataRequired()], render_kw = {"placeholder": "Enter your password", "title": "Enter your password"})
	submit = SubmitField(label = "Sign In", render_kw = {"title": "Sign in now"})

class AddTask(db.Model):
	id = db.Column(db.Integer, primary_key = True)
	user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable = False)
	content = db.Column(db.String(200), nullable = False)
	is_new = db.Column(db.Boolean, default = True)
	is_completed = db.Column(db.Boolean, default = False)
	date_created = db.Column(db.DateTime, default = datetime.utcnow)
	date_completed = db.Column(db.DateTime, default = datetime.utcnow)

	def __repr__(self):
		return f"Task {self.id}"

# Routes
@app.route("/register", methods = ["GET", "POST"])
def register():
	form = RegisterForm()

	if (form.validate_on_submit()):
		new_user = User(username = form.username.data, password = form.password1.data)
		db.session.add(new_user)
		db.session.commit()
		login_user(new_user)
		flash(f"Account created successfully! You are logged in as: {new_user.username}", category = "success")
		return redirect(url_for("index"))
		
	if (form.errors != {}):
		for err_msg in form.errors.values():
			flash(f"There was an error with creating a new user-account: {err_msg}", category = "danger")

	return render_template("register.html", form = form)

@app.route("/login", methods = ["GET", "POST"])
def login():
	form = LoginForm()

	if (form.validate_on_submit()):
		attempted_user = User.query.filter_by(username = form.username.data).first()
		if (attempted_user and attempted_user.check_password_correction(attempted_password = form.password.data)):
			login_user(attempted_user)
			flash(f"Success! You are logged in as: {attempted_user.username}", category = "success")
		return redirect(url_for("index"))
	else:
		flash("Username and password are not match! Please try again", category = "danger")
		
	if (form.errors != {}):
		for err_msg in form.errors.values():
			flash(f"There was an error with creating a new user-account: {err_msg}", category = "danger")

	return render_template("login.html", form = form)

@app.route("/logout")
@login_required
def logout():
	logout_user()
	flash("You have been logged out!", category = "info")
	return redirect(url_for("index"))

@app.route("/", methods = ["GET", "POST"])
@login_required
def index():
	if (request.method == "POST"):
		task_content = request.form["content"]
		new_task = AddTask(content = task_content, user_id = current_user.id)

		try:
			db.session.add(new_task)
			db.session.commit()
		except:
			flash("There was an issue adding your task!", category = "danger")
		return redirect(url_for("index"))
	else:
		tasks = AddTask.query.filter(AddTask.user_id == current_user.id, AddTask.is_completed != True).order_by(AddTask.date_created.desc()).all()
		tasks_completed = AddTask.query.filter(AddTask.user_id == current_user.id, AddTask.is_completed).order_by(AddTask.date_completed.desc()).all()
		return render_template("index.html", tasks = tasks, tasks_completed = tasks_completed)
	
@app.route("/complete/<int:id>")
@login_required
def complete(id):
	task = AddTask.query.get_or_404(id)

	if (task.user_id != current_user.id):
		flash("You are not authorized to complete this task!", category = "danger")
		return redirect(url_for("index"))

	task.is_completed = True
	task.date_completed = datetime.utcnow()

	try:
		db.session.commit()
	except:
		flash("There was an issue make your task complete!", category = "danger")
	return redirect(url_for("index"))
	
@app.route("/edit/<int:id>", methods = ["GET", "POST"])
@login_required
def edit(id):
	task = AddTask.query.get_or_404(id)

	if (task.user_id != current_user.id):
		flash("You are not authorized to edit this task!", category = "danger")
		return redirect(url_for("index"))

	if (request.method == "POST"):
		task.content = request.form["content"]
		task.date_created = datetime.utcnow()

		try:
			db.session.commit()
		except:
			flash("There was an issue editing your task!", category = "danger")
		return redirect(url_for("index"))
	else:
		task.is_new = False
		db.session.commit()
		return render_template("edit.html", task = task)
	
@app.route("/delete/<int:id>")
@login_required
def delete(id):
	task = AddTask.query.get_or_404(id)

	if (task.user_id != current_user.id):
		flash("You are not authorized to delete this task!", category = "danger")
		return redirect(url_for("index"))

	try:
		db.session.delete(task)
		db.session.commit()
	except:
		flash("There was an issue deleting your task!", category = "danger")
	return redirect(url_for("index"))

if (__name__ == "__main__"):
	app.run(debug = True)