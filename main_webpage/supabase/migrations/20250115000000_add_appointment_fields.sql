-- Add missing fields to appointments table for calendar functionality
-- This migration adds customer_name, job_type, and technician fields

-- Add the new columns to the appointments table
ALTER TABLE appointments 
ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS job_type VARCHAR(255),
ADD COLUMN IF NOT EXISTS technician VARCHAR(255);

-- Add comments for documentation
COMMENT ON COLUMN appointments.customer_name IS 'Name of the customer for the appointment';
COMMENT ON COLUMN appointments.job_type IS 'Type of service/job being performed';
COMMENT ON COLUMN appointments.technician IS 'Name of the technician assigned to the appointment';

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_appointments_customer_name ON appointments(customer_name);
CREATE INDEX IF NOT EXISTS idx_appointments_job_type ON appointments(job_type);
CREATE INDEX IF NOT EXISTS idx_appointments_technician ON appointments(technician);
CREATE INDEX IF NOT EXISTS idx_appointments_salon_id_date ON appointments(salon_id, appointment_date);
