from flask import request, jsonify
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from app import app, db
from app.models import User
from app.config import JWT_SECRET_KEY

import jwt

@app.route("/api/v1/auth/signin", methods=["POST"])
def signin():
    if (
        request.method == "POST"
        and "email" in request.form
        and "password" in request.form
    ):
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({"msg": "Email address not found"}), 404

        if not check_password_hash(user.password, password):
            return jsonify({"msg": "Incorrect password"}), 401
        
        if user.status == 'Inactive':
            return jsonify({"msg": "User is not permitted. Please wait until the admin approves"}), 400

        try:
            payload = {
                'exp': datetime.utcnow() + timedelta(hours=1),
                'iat': datetime.utcnow(),
                'sub': user.id
            }

            token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

            return jsonify({
                "msg": "Login successful",
                "token": token,
                "user": user.to_dict()
            }), 200

        except Exception as e:
            print(f"Token generation failed: {e}")
            return jsonify({"msg": "Token generation failed"}), 500

    else:
        return jsonify({"status": 400, "msg": "Missing fields"}), 400

@app.route("/api/v1/auth/signup", methods=["POST"])
def signup():
    if (
        request.method == "POST"
        and "name" in request.form
        and "email" in request.form
        and "password" in request.form
    ):
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        existing_user = User.query.filter_by(email=email).first()
        
        if existing_user:
            return jsonify({"msg": "User already registered."}), 409

        new_user = User(name=name, email=email, password=password)
        
        try:
            db.session.add(new_user)
            db.session.commit()

            return jsonify({"msg": "User Registered successfully"}), 200
        except Exception as e:
            print(f"Database operation failed due to {e}")
            db.session.rollback()
            return jsonify({"msg": "Database Error"}), 400
    else:
        return jsonify({"status": 400, "msg": "Missing fields"}), 400
    
@app.route("/api/v1/users/get-users", methods=["GET"])
def get_users():
    search = request.args.get('search')
    status = request.args.get('status')
    page = request.args.get('page', type=int, default=1)
    size = request.args.get('size', type=int, default=10)

    query = User.query

    if search:
        query = query.filter(User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))

    if status and status != '*':
        if status == 'Active':
            query = query.filter(User.status == 'Active')
        elif status == 'Inactive':
            query = query.filter(User.status == 'Inactive')

    offset = (page - 1) * size
    filtered_users = query.offset(offset).limit(size).all()

    total_users_count = User.query.count()

    response = {
        "total_users_count": total_users_count,
        "users": [user.to_dict() for user in filtered_users]
    }

    return jsonify(response), 200

@app.route("/api/v1/admin/add-user", methods=["POST"])
def add_user():
    if (
        request.method == "POST"
        and "name" in request.form
        and "email" in request.form
        and "status" in request.form
    ):
        name = request.form["name"]
        email = request.form["email"]
        status = request.form["status"]
        password = generate_password_hash("111111")

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return jsonify({"msg": "User already exists with this email."}), 409
        
        new_user = User(name=name, email=email, password=password, status=status)

        try:
            db.session.add(new_user)
            db.session.commit()

            return jsonify({"msg": "User Created successfully"}), 200
        except Exception as e:
            print(f"Database operation failed due to {e}")
            db.session.rollback()
            return jsonify({"msg": "Database Error"}), 400
    else:
        return jsonify({"status": 400, "message": "Missing fields"}), 400

@app.route("/api/v1/admin/update-user", methods=["POST"])
def update_user():
    if (
        request.method == "POST"
        and "id" in request.form
        and "name" in request.form
        and "email" in request.form
        and "status" in request.form
    ):
        user_id = request.form["id"]
        name = request.form["name"]
        email = request.form["email"]
        status = request.form["status"]

        # Fetch the user by ID
        user = User.query.get(user_id)

        if not user:
            return jsonify({"msg": "User not found."}), 404

        # Update user details
        user.name = name
        user.email = email
        user.status = status

        try:
            db.session.commit()
            return jsonify({"msg": "User updated successfully."}), 200
        except Exception as e:
            print(f"Database operation failed due to {e}")
            db.session.rollback()
            return jsonify({"msg": "Database error occurred during update."}), 500

    return jsonify({"msg": "Invalid request. Missing required fields."}), 400

@app.route("/api/v1/admin/delete-user/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        user = User.query.get(user_id)

        if not user:
            return jsonify({"msg": "User not found"}), 404

        db.session.delete(user)
        db.session.commit()

        return jsonify({"msg": f"User has been deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "An error occurred while deleting the user", "error": str(e)}), 500