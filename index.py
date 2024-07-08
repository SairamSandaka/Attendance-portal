from flask import Flask, redirect, url_for, render_template, request, session, flash,jsonify
from datetime import timedelta, datetime
import pandas as pd
import os
from pymongo import MongoClient

def time_to_seconds(time_str):
    hours, minutes, seconds = map(int, time_str.split(':'))
    return hours * 3600 + minutes * 60 + seconds

def is_present(attendedtime, total):
    percent = (attendedtime / total) * 100
    return percent >= 85

# MongoDB Configuration
client = MongoClient('mongodb://localhost:27017/')
db = client['college']
students_collection = db['students']
teachers_collection = db['teachers']

app = Flask(__name__)

app.secret_key = "secret_key"
app.permanent_session_lifetime = timedelta(days=3650*100)

@app.route("/")
def hello():
    if "user" in session:
        name = session["user"]
        students_data = students_collection.find()
        return render_template("content.html",data = students_data,user=name,date= None,selected=False)
    else:
        return render_template("login.html")

@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        session.permanent = True
        user = request.form["username"]
        password = request.form['password']

        result = teachers_collection.find_one({"Name":user,"Password":password})
        if result is not None:
            session["user"] = user
            user = session["user"]
            session['email']=result["Email"]
            session['course']=result['Course']
            students_data = students_collection.find({"Course":result['Course']})
            return redirect(url_for("hello",data = students_data,user = user,date= None,selected=False))
        return render_template("login.html")
    return render_template("login.html")


@app.route("/signup",methods=["POST","GET"])
def signup():
    if request.method == "POST":
        user = request.form["name"]
        password = request.form["password"]
        email = request.form['email']
        course = request.form['course']
        sections = request.form['sections']
        session['sections']=int(sections)
        sections = int(sections)
        session['course']=course
        for i in range(1,int(sections)+1):
            students = request.files['file'+str(i)]
            students_df = pd.read_csv(students)
            for index, row in students_df.iterrows():
                student_data = {
                    'Roll No': row['Roll No'],
                    'Student Name': row['Student Name'],
                    'Section': 'Section'+ str(i),
                    'Course':course
                }
                students_collection.insert_one(student_data)
        teacher_details={
            'Name':user,
            'Email':email,
            'Password':password,
            'Course':course,
        }
        teachers_collection.insert_one(teacher_details)
        students_data = students_collection.find({"Course":session['course']})
        return redirect(url_for("hello",data = students_data,user = user,date= None,selected=False))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


@app.route('/upload', methods=['POST'])
def upload_files():
    if request.method == 'POST':
        section = request.form['section']
        date = request.form['date']
        if 'attendance_list' not in request.files:
            return 'No file part'

        attendance_list = request.files['attendance_list']

        if attendance_list.filename == '':
            return 'No selected file'

        # Ensure the 'uploads' directory exists
        if not os.path.exists('uploads'):
            os.makedirs('uploads')

        # Save the uploaded files to the 'uploads' directory
        attendance_list_path = os.path.join('uploads', attendance_list.filename)

        attendance_list.save(attendance_list_path)

        df = pd.read_csv(attendance_list_path, skiprows=4)
        df1 = pd.read_csv(attendance_list_path, nrows=4, header=None)

        present = []
        start = df1.iloc[2, 0].split()[-1]
        end = df1.iloc[3, 0].split()[-1]

        time1 = datetime.strptime(start, '%H:%M:%S')
        time2 = datetime.strptime(end, '%H:%M:%S')

        time_gap = (time2 - time1).total_seconds()

        for i in range(len(df)):
            value = df.loc[i, "Time in Call"]
            value = time_to_seconds(value)
            if is_present(value, time_gap):
                df.loc[i, "status"] = "Present"
                present.append(df.loc[i, "Full Name"])
            else:
                df.loc[i, "status"] = "Not present"

        students_in_section = list(students_collection.find({"Section": section,"Course":session['course']}))

        for student in students_in_section:
            student_name = student['Student Name']
            if student_name in present:
                status = "Present"
            else:
                status = "Not present"

            students_collection.update_one(
                {"Student Name": student_name, "Section": section,"Course":session['course']},
                {"$push": {"status": {date : status}}},
                upsert=True
            )
            # Recalculate attendance percentage
            updated_student = students_collection.find_one({"Student Name": student_name, "Section": section,"Course":session['course']})
            status_list = updated_student.get('status', [])
            total_classes = len(status_list)
            present_count = sum(1 for status in status_list if list(status.values())[0] == "Present")
            attendance_percentage = (present_count / total_classes) * 100 if total_classes > 0 else 0

            students_collection.update_one(
                {"Student Name": student_name, "Section": section,"Course":session['course']},
                {"$set": {"percentage": attendance_percentage}}
            )

        flash('uploaded successfully!', 'success')
        students_data = students_collection.find({"Course":session['course']})
        return redirect(url_for("hello", data = students_data,user = session['user'],date= None,selected=False))

@app.route("/all",methods=["GET", "POST"])
def all():
    if request.method == "POST":
        if(request.form['section']=="all"):
            students_data = students_collection.find({"Course":session['course']})
            # return redirect(url_for("hello", data = students_data,user = session['user']))
        else:
            students_data = students_collection.find({"Section":request.form['section'],"Course":session['course']})
        return render_template("content.html", data = students_data,user = session['user'],date= None,selected=False)
    # else:
    #     students_data = students_collection.find()
    #     return redirect(url_for("hello", data = students_data,user = session['user']))
@app.route("/selected_date", methods=["POST"])
def selected_date():
    if request.method == "POST":
        selected_date = request.form.get("date")
        print("Selected date:", selected_date)
        students_data = students_collection.find({"Course":session['course']})
        return render_template("content.html", data=students_data, user=session['user'], date=selected_date, selected=True)
    else:
        return "hello"

if __name__ == "__main__":
    app.run(debug=True)
