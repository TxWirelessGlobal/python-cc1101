import cc1101
import time
# import RPi.GPIO as GPIO
import sys
from cc1101 import StrobeAddress, ConfigurationRegisterAddress, StatusRegisterAddress

CSN_PIN = 23

FREQ = (
    float(sys.argv[1]) * 1e6 if len(sys.argv) > 1 else 433.92e6
)  # Default to 433.92 MHz

# GPIO.setmode(GPIO.BCM)
# GPIO.setup(CSN_PIN, GPIO.OUT)
# GPIO.output(CSN_PIN, GPIO.HIGH)


def write_register(trx, reg, val):
    # GPIO.output(CSN_PIN, GPIO.LOW)
    time.sleep(0.001)
    trx._spi.xfer([reg | 0x00, val])  # single write
    # GPIO.output(CSN_PIN, GPIO.HIGH)


with cc1101.CC1101(0, 1) as trx:
    trx.set_base_frequency_hertz(FREQ)
    trx.set_output_power([0xC0])  # 10 dBm

    # Enter CW mode
    write_register(trx, ConfigurationRegisterAddress.MDMCFG2, 0x30)  # unmodulated
    # Set RX Bandwidth to 541 kHz (0x2C) to reduce noise (was 812 kHz)
    write_register(trx, ConfigurationRegisterAddress.MDMCFG4, 0x2C)
    
    # Optimization for sensitivity and 830 MHz operation
    write_register(trx, ConfigurationRegisterAddress.FSCTRL1, 0x06)
    
    # Reduced AGC Target to 33dB (0x03) to lower noise floor (was 0x07 / 42dB)
    write_register(trx, ConfigurationRegisterAddress.AGCTRL2, 0x03)
    write_register(trx, ConfigurationRegisterAddress.AGCTRL1, 0x00)
    write_register(trx, ConfigurationRegisterAddress.AGCTRL0, 0x91)
    
    write_register(trx, ConfigurationRegisterAddress.FREND1, 0xB6)
    write_register(trx, ConfigurationRegisterAddress.FREND0, 0x11)
    write_register(trx, ConfigurationRegisterAddress.FSCAL3, 0xE9)
    write_register(trx, ConfigurationRegisterAddress.FSCAL2, 0x2A)
    write_register(trx, ConfigurationRegisterAddress.FSCAL1, 0x00)
    write_register(trx, ConfigurationRegisterAddress.FSCAL0, 0x1F)
    
    # Reverted TEST registers to defaults to avoid forcing high gain/current
    # write_register(trx, ConfigurationRegisterAddress.TEST2, 0x81)
    # write_register(trx, ConfigurationRegisterAddress.TEST1, 0x35)
    # write_register(trx, ConfigurationRegisterAddress.TEST0, 0x09)

    write_register(
        trx, ConfigurationRegisterAddress.PKTCTRL0, 0x32
    )  # Async serial mode, infinite length (prevents FIFO overflow)
    write_register(
        trx, ConfigurationRegisterAddress.IOCFG0, 0x06
    )  # Optional: GDO0 to sync

    # STX to enter TX mode
    trx._command_strobe(StrobeAddress.SIDLE)  # Ensure idle first
    trx._command_strobe(StrobeAddress.SFRX)  # Flush RX FIFO
    trx._command_strobe(StrobeAddress.SRX)

    print(f"Receiving CW at {FREQ / 1e6} MHz. Press Ctrl+C to stop.")
    try:
        while True:
            max_rssi = -128.0
            start_time = time.time()
            # Sample for 0.1 seconds and find the peak RSSI
            while time.time() - start_time < 0.1:
                rssi_byte = trx._read_status_register(StatusRegisterAddress.RSSI)
                if rssi_byte >= 128:
                    rssi_dbm = (rssi_byte - 256) / 2 - 74
                else:
                    rssi_dbm = rssi_byte / 2 - 74
                if rssi_dbm > max_rssi:
                    max_rssi = rssi_dbm
            
            print(f"Peak RSSI: {max_rssi:.1f} dBm")
            
            # Debug: Check MARCSTATE to ensure we are in RX
            marcstate = trx._read_status_register(StatusRegisterAddress.MARCSTATE) & 0x1F
            if marcstate != 0x0D: # 0x0D is RX
                 print(f"Warning: MARCSTATE is {marcstate} (not RX)")
                 trx._command_strobe(StrobeAddress.SIDLE)
                 trx._command_strobe(StrobeAddress.SFRX) # Flush RX FIFO
                 trx._command_strobe(StrobeAddress.SRX)

    except KeyboardInterrupt:
        print("Stopping.")
        trx._command_strobe(StrobeAddress.SIDLE)
