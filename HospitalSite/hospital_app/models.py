
from django.db import models

class Patient(models.Model):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    dob = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "hospital_app"
        db_table = "hospital_patient"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    appointment_date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "hospital_app"
        db_table = "hospital_appointment"

    def __str__(self):
        return f"Appointment for {self.patient} on {self.appointment_date}"
