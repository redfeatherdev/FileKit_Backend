import os

from flask import request, jsonify
from datetime import datetime

from app import app, db
from app.models import Template

@app.route("/api/v1/admin/get-templates", methods=["GET"])
def get_templates():
    search = request.args.get('search')
    page = request.args.get('page', type=int, default=1)
    size = request.args.get('size', type=int, default=10)

    query = Template.query

    if search:
        query = query.filter(Template.name.ilike(f'%{search}%'))

    offset = (page - 1) * size
    filtered_templates = query.offset(offset).limit(size).all()

    total_count = Template.query.count()

    response = {
        "total_count": total_count,
        "templates": [template.to_dict() for template in filtered_templates]
    }

    return jsonify(response), 200

@app.route("/api/v1/admin/add-template", methods=["POST"])
def add_template():
    if request.method == "POST":
        if 'files' not in request.files:
            return jsonify({"msg": 'No files part in the request'}), 400

        files = request.files.getlist('files')

        if not files:
            return jsonify({'msg': 'No files selected'}), 400

        saved_files = []

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_upload_folder = os.path.abspath("./uploads")
            timestamped_folder = os.path.join(base_upload_folder, timestamp)
            os.makedirs(timestamped_folder, exist_ok=True)

            for file in files:
                if file.filename == '':
                    continue

                original_filename = file.filename
                file_name, file_extension = os.path.splitext(original_filename)
                file_extension = file_extension.lstrip('.')

                file_size = len(file.read())
                file.seek(0)

                file_path = os.path.join(timestamped_folder, original_filename)
                file.save(file_path)

                # Add to the database
                new_template = Template(
                    name=file_name,
                    type=file_extension,
                    size=file_size,
                    path=file_path
                )
                db.session.add(new_template)

                # Add to the response
                saved_files.append({
                    "name": file_name,
                    "type": file_extension,
                    "path": file_path
                })

            db.session.commit()

            return jsonify({
                "msg": "Templates uploaded and saved successfully",
                "files": saved_files
            }), 200
        except Exception as e:
            print(f"Database operation failed due to {e}")
            db.session.rollback()
            return jsonify({"msg": "Database Error", "error": str(e)}), 500
    else:
        return jsonify({"status": 400, "message": "Invalid request method"}), 400