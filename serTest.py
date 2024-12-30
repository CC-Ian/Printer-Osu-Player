import serial
import time

# Define the serial port and baudrate
serial_port = '/dev/ttyUSB1'  # Change this to the correct port for your setup
baud_rate = 115200  # Adjust the baud rate based on your 3D printer's specifications

# Open the serial port
ser = serial.Serial(serial_port, baud_rate, timeout=1)

# Ensure the serial port is open
if ser.is_open:
    print(f"Connected to {serial_port} at {baud_rate} baud.")
else:
    print(f"Failed to open {serial_port}.")
    exit()

try:
    # Send a command to the 3D printer
    command = "G28\n"  # Home all axes
    ser.write(command.encode('utf-8'))
    
    # Wait for the printer to respond (adjust as needed)
    time.sleep(2)

    # Read and print the response
    response = ser.readline().decode('utf-8')
    print(f"Response from the printer: {response}")

except Exception as e:
    print(f"An error occurred: {str(e)}")

finally:
    # Close the serial port
    ser.close()
    print("Serial port closed.")