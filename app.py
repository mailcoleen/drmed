from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinic_queue.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------
# DATABASE MODEL
# ---------------------------------------------------------
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    room = db.Column(db.String(20), nullable=False)
    time_registered = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default="Waiting")   # Waiting, Called, Done
    called_seq = db.Column(db.Integer, default=0)          # Increases on CALL or RECALL


# ---------------------------------------------------------
# ENSURE DATABASE + LIGHT MIGRATION
# ---------------------------------------------------------
with app.app_context():
    db.create_all()

    insp = inspect(db.engine)
    cols = [c['name'] for c in insp.get_columns('patient')]

    # Add missing column (old DB)
    if "called_seq" not in cols:
        with db.engine.connect() as con:
            con.execute(text(
                "ALTER TABLE patient ADD COLUMN called_seq INTEGER DEFAULT 0"
            ))
            con.commit()


# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

# ---------------- HOME (REGISTRATION) ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        room = request.form.get('room', '')

        if name and room:
            db.session.add(Patient(name=name, room=room))
            db.session.commit()

        return redirect(url_for('index'))

    # Rooms to show in dropdown (including special areas)
    rooms = [
        ('1', 'Room 1'),
        ('2', 'Room 2'),
        ('3', 'Room 3'),
        ('4', 'Room 4'),
        ('5', 'Room 5'),
        ('Extraction', 'Extraction Area'),
        ('Xray', 'X-ray Room'),
        ('ECG', 'ECG / Ultrasound')
    ]
    return render_template('index.html', rooms=rooms)


# ---------------- ADMIN PANEL ----------------
@app.route('/admin')
def admin():
    # Newest first is easier for staff
    patients = Patient.query.order_by(Patient.id.desc()).all()
    return render_template('admin.html', patients=patients)


# ---------------- CALL PATIENT ----------------
@app.route('/call/<int:patient_id>')
def call(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    patient.status = "Called"
    patient.called_seq = (patient.called_seq or 0) + 1
    db.session.commit()
    return redirect(url_for('admin'))


# ---------------- RECALL PATIENT ----------------
@app.route('/recall/<int:patient_id>')
def recall(patient_id):
    patient = Patient.query.get_or_404(patient_id)

    if patient.status != "Called":
        patient.status = "Called"

    patient.called_seq = (patient.called_seq or 0) + 1
    db.session.commit()

    return redirect(url_for('admin'))


# ---------------- MARK DONE ----------------
@app.route('/done/<int:patient_id>')
def done(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    patient.status = "Done"
    db.session.commit()
    return redirect(url_for('admin'))


# ---------------- DELETE PATIENT ----------------
@app.route('/delete/<int:patient_id>')
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    db.session.delete(patient)
    db.session.commit()
    return redirect(url_for('admin'))


# ---------------- API FOR DISPLAY ----------------
@app.route('/api/current')
def current():
    # Order here MUST match the order used in display.html JS
    rooms = ['1', '2', '3', '4', '5', 'Extraction', 'Xray', 'ECG']
    result = []

    for room in rooms:
        p = (
            Patient.query
            .filter_by(room=room, status="Called")
            .order_by(Patient.called_seq.desc(), Patient.id.desc())
            .first()
        )

        if p:
            result.append({
                "id": p.id,
                "name": p.name,
                "room": p.room,
                "token": p.called_seq   # used to re-trigger TTS on recall
            })
        else:
            result.append(None)

    return jsonify(result)


# ---------------- DISPLAY SCREEN ----------------
@app.route('/display')
def display():
    return render_template('display.html')


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
