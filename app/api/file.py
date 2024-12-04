import os
import pandas as pd
import nest_asyncio
import uuid
from flask import request, jsonify, send_file
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_parse import LlamaParse
from datetime import datetime
from PyPDF2 import PdfReader

from app.config import LLAMA_API_KEY, OPENAI_API_KEY
from app.models import File
from app import app, db

nest_asyncio.apply()

@app.route("/api/v1/file/scan", methods=["POST"])
def scan_file():
    try:
        if 'files' not in request.files:
            return jsonify({"msg": "No files part in the request"}), 400

        files = request.files.getlist("files")
        if not files:
            return jsonify({"msg": "No files uploaded"}), 400

        userId = request.form["userId"]
        if not userId:
            return jsonify({"msg": "UnAuthorized request"}), 401

        uploaded_file_path = None
        for file in files:
            filename = file.filename
            uploaded_file_path = os.path.abspath(f"./templates/{filename}")
            file.save(uploaded_file_path)

            pdf_reader = PdfReader(uploaded_file_path)
            total_pages = len(pdf_reader.pages)

        if not uploaded_file_path:
            return jsonify({"msg": "Failed to save uploaded file"}), 500

        llama_parse = LlamaParse(
            api_key=LLAMA_API_KEY,
            language="en",
            result_type="markdown",
            parsing_instruction=(
                "The provided file is an invoice containing supplier and program details, invoice numbers, and itemized purchase data. "
                "Extract the following data in a structured format: "
                "1. Supplier details: name, address, contact information. "
                "2. Invoice details: invoice number, date, total amount, and program details (including program ID and description). "
                "3. Itemized purchases: product name, brand, pack size, description, product ID, DID, UPC, quantities, total price, "
                "FOB, DEL, program amount, and amount."
                "Organize the data as a structured table for itemized purchases and a summary for totals. "
                "Ensure all monetary values are captured accurately. Mathematical equations are not present and should be ignored. "
                "Use plain markdown to format the output, with tables for structured data."
            ),
        )

        documents = llama_parse.load_data([uploaded_file_path])

        embedding = OpenAIEmbedding(openai_api_key=OPENAI_API_KEY)

        index = VectorStoreIndex.from_documents(documents, embed_model=embedding)
        query_engine = index.as_query_engine()

        response = query_engine.query(
            str_or_query_bundle="Extract all itemized purchase data and totals as structured tables."
        )

        markdown_content = str(response)

        dataframes = []
        for table in markdown_content.split("\n\n"):
            if "|" in table:
                rows = [row.strip().split("|") for row in table.split("\n") if "|" in row]
                headers = [h.strip() for h in rows[0][1:-1]]
                data = [row[1:-1] for row in rows[2:]]

                for row in data:
                    if len(row) < len(headers):
                        row.extend([""] * (len(headers) - len(row)))

                df = pd.DataFrame(data, columns=headers)
                dataframes.append(df)

        combined_table = pd.concat(dataframes, ignore_index=True)

        unique_csv_name = f"output_invoice_data_{uuid.uuid4().hex}.csv"
        output_csv_path = os.path.abspath(f"./templates/{unique_csv_name}")

        combined_table.to_csv(output_csv_path, index=False)

        new_file = File(
            name = unique_csv_name,
            path = output_csv_path,
            total_pages = total_pages,
            user_id = userId
        )

        db.session.add(new_file)
        db.session.commit()

        if uploaded_file_path and os.path.exists(uploaded_file_path):
            os.remove(uploaded_file_path)

        return jsonify({"msg": "CSV created successfully.", "csv_path": output_csv_path}), 200

    except Exception as e:
        if uploaded_file_path and os.path.exists(uploaded_file_path):
            os.remove(uploaded_file_path)
        return jsonify({"msg": f"Error processing file: {str(e)}"}), 500

@app.route("/api/v1/file/get-files", methods=["GET"])
def get_files():
    page = request.args.get('page', type=int, default=1)
    size = request.args.get('size', type=int, default=10)
    user_id = request.args.get('userId', type=int)
    try:
        query = File.query
        if user_id:
            query = query.filter_by(user_id=user_id)

        paginated_files = query.paginate(page=page, per_page=size, error_out=False)
        total_files_count = query.count()

        file_list = []
        for file in paginated_files.items:
            file_list.append({
                "id": file.id,
                "name": file.name,
                "path": file.path,
                "created_at": file.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "total_pages": file.total_pages,
            })

        return jsonify({
            "files": file_list,
            "total_files_count": total_files_count,
            "current_page": paginated_files.page,
            "total_pages": paginated_files.pages,
            "message": "Files retrieved successfully"
        })

    except Exception as e:
        return jsonify({
            "message": f"Error occurred: {str(e)}"
        }), 500

@app.route("/api/v1/file/get-all-files", methods=["GET"])
def get_all_files():
    page = request.args.get('page', type=int, default=1)
    size = request.args.get('size', type=int, default=10)
    
    try:
        query = File.query

        paginated_files = query.paginate(page=page, per_page=size, error_out=False)
        total_files_count = query.count()

        file_list = []
        for file in paginated_files.items:
            user = file.user

            file_list.append({
                "id": file.id,
                "name": file.name,
                "path": file.path,
                "created_at": file.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "total_pages": file.total_pages,
                "name": user.name
            })

        return jsonify({
            "files": file_list,
            "total_files_count": total_files_count,
            "current_page": paginated_files.page,
            "total_pages": paginated_files.pages,
            "message": "Files retrieved successfully"
        })

    except Exception as e:
        return jsonify({
            "message": f"Error occurred: {str(e)}"
        }), 500

@app.route("/api/v1/file/download/<int:file_id>", methods=["GET"])
def download_file(file_id):
    try:
        file_record = File.query.get(file_id)
        if not file_record:
            return jsonify({"msg": "File not found"}), 404

        file_path = file_record.path

        if not os.path.exists(file_path):
            return jsonify({"msg": "File does not exist on the server"}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_record.name,
            mimetype="text/csv"
        )

    except Exception as e:
        return jsonify({"msg": f"Error downloading file: {str(e)}"}), 500

@app.route("/api/v1/admin/delete-file/<int:file_id>", methods=["DELETE"])
def delete_file(file_id):
    try:
        file = File.query.get(file_id)

        if not file:
            return jsonify({"msg": "File not found"}), 404

        file_path = file.path

        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            return jsonify({"msg": "File not found on the server"}), 404

        db.session.delete(file)
        db.session.commit()

        return jsonify({"msg": "File and its record have been deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "An error occurred while deleting the file", "error": str(e)}), 500