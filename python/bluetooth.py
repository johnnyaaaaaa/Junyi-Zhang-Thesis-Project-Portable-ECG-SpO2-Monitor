"""
bluetooth.py

This script is used to manage Bluetooth communication in a Python application. It uses the Bleak library for
Bluetooth Low Energy (BLE) communication and the asyncio library for asynchronous programming.

The script defines a class, BluetoothManager, which is responsible for managing the Bluetooth communication. The
class has several methods:

- __init__(self, device_name=None, mac_address=None, uuid=None, ui=None, dialog=None): This is the constructor
method. It initializes the BluetoothManager with the given device name, MAC address, UUID, user interface, and dialog.

- connect_by_device_name(self): This method connects to a Bluetooth device by its name. It returns the MAC address of
the device if found, None otherwise.

- connect_and_start_notifications(self): This method connects to a Bluetooth device and starts receiving
notifications. If the MAC address is not provided, it attempts to connect by device name.

- wait_for_notifications(self): This method keeps the connection alive and waits for notifications.

- notification_handler(self, sender, data): This method handles incoming notifications. It processes the data
received in the notification.

- cleanup(self): This method cleans up the connection and stops notifications.

- start_scan(self): This method starts a scan for Bluetooth devices in a background thread.

- scan_for_devices(self): This method asynchronously scans for Bluetooth devices and updates the scan results in the UI.

- start(self): This method starts the BluetoothManager, connects to a device, and starts receiving notifications.

- shut(self): This method asynchronously shuts down the event loop safely. It returns True if the connection was
closed successfully, False otherwise.

- stop(self): This method stops the manager and disconnects.

To use this script, you need to create an instance of the BluetoothManager class, passing the device name,
MAC address, UUID, user interface, and dialog to the constructor. Then, you can use the start method to start the
Bluetooth communication, the stop method to stop it, and the start_scan method to scan for Bluetooth devices.
"""

import asyncio
from process_data import process_data
from bleak import BleakClient, BleakScanner


class BluetoothManager:
    """
    Class to manage Bluetooth communication.
    """

    def __init__(self, device_name=None, mac_address=None, uuid=None, ui=None, dialog=None):
        """
        Initialize the BluetoothManager with the given device name, MAC address, UUID, user interface, and dialog.

        Parameters:
        - device_name: The name of the Bluetooth device to connect to.
        - mac_address: The MAC address of the Bluetooth device to connect to.
        - uuid: The UUID of the Bluetooth service to connect to.
        - ui: The user interface to interact with.
        - dialog: The dialog to display messages in.
        """
        self.device_name = device_name
        self.mac_address = mac_address
        self.uuid = uuid
        self.ui = ui
        self.dialog = dialog
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = None

    async def connect_by_device_name(self):
        """
        Connect to a Bluetooth device by its name.

        Returns:
        - The MAC address of the device if found, None otherwise.
        """
        devices = await BleakScanner.discover()
        for device in devices:
            if device.name == self.device_name:
                print(f"Found device with name {self.device_name}: {device.address}")
                return device.address
        print(f"No device with name {self.device_name} found.")
        return None

    async def connect_and_start_notifications(self):
        """
        Connect to a Bluetooth device and start receiving notifications.

        If the MAC address is not provided, it attempts to connect by device name.
        """
        self.dialog.update_status_signal.emit("Attempting to connect...")
        if self.mac_address is None and self.device_name:
            self.mac_address = await self.connect_by_device_name()
            if self.mac_address is None:
                self.dialog.update_status_signal.emit("No suitable device found.")
                return

        if self.mac_address:
            self.client = BleakClient(self.mac_address, loop=self.loop)
            try:
                if await self.client.connect():
                    try:
                        device_name = await self.client.read_gatt_char('00002a00-0000-1000-8000-00805f9b34fb')
                        device_name = device_name.decode('utf-8')
                    except Exception as e:
                        device_name = "Unknown Device"
                    message = f"Successfully connected to address:{self.mac_address} name:({device_name})"
                    self.dialog.update_status_signal.emit(message)
                    self.ui.ble_status_signal.emit(f"BLE connected on {device_name}", "green")
                    await asyncio.sleep(2)
                    await self.client.start_notify(self.uuid, self.notification_handler)
                    await self.wait_for_notifications()
                else:
                    self.dialog.update_status_signal.emit(f"Failed to connect to {self.mac_address}")
                    await asyncio.sleep(2)
            except Exception as e:
                self.dialog.update_status_signal.emit(f"Connection failed: {str(e)}")
                await asyncio.sleep(2)

    async def wait_for_notifications(self):
        """
        Keep the connection alive and wait for notifications.
        """
        try:
            while True:
                await asyncio.sleep(3600)  # Keep the connection alive
        except asyncio.CancelledError:
            print("Notification handling canceled.")

    def notification_handler(self, sender, data):
        """
        Handle incoming notifications.

        Parameters:
        - sender: The sender of the notification.
        - data: The data received in the notification.
        """
        for byte in data:
            if self.ui.is_receiving_data:
                if not self.ui.is_serial_connected:
                    process_data(byte, self.ui)
                elif self.ui.is_serial_connected and self.ui.using_ble:
                    process_data(byte, self.ui)

    async def cleanup(self):
        """
        Clean up the connection and stop notifications.
        """
        if self.client and self.client.is_connected:
            await self.client.stop_notify(self.uuid)
            await self.client.disconnect()
        print("Disconnected and notification stopped.")

    def start_scan(self):
        """
        Start a scan for Bluetooth devices in a background thread.
        """
        if not self.loop.is_running():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.scan_for_devices())
        else:
            asyncio.run_coroutine_threadsafe(self.scan_for_devices(), self.loop)

    async def scan_for_devices(self):
        """
        Asynchronously scan for Bluetooth devices and update the scan results in the UI.
        """
        try:
            devices = await BleakScanner.discover()
            if devices:
                for device in devices:
                    if device.name:
                        device_info = f"Device found: {device.name}, Address: {device.address}"
                        print(device_info)
                        self.dialog.update_status_signal.emit(device_info)
            else:
                print("No devices found.")
                self.dialog.update_status_signal.emit("No devices found.")
        except Exception as e:
            print(f"Error scanning devices: {e}")

    def start(self):
        """
        Start the BluetoothManager and connect to a device and start receiving notifications.
        """
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_and_start_notifications())
        self.loop.close()

    async def shut(self):
        """
        Asynchronously shut down the event loop safely.

        Returns:
        - True if the connection was closed successfully, False otherwise.
        """
        try:
            if self.client.is_connected:
                await self.client.disconnect()
                print("Disconnected successfully.")
                return True
        except Exception as e:
            print(f"Failed to disconnect: {e}")
            return False

    def stop(self):
        """
        Stop the manager and disconnect.
        """
        future = asyncio.run_coroutine_threadsafe(self.shut(), self.loop)
        try:
            # Wait for the Future to complete and get the result
            result = future.result(timeout=10)  # You can set a timeout
            if result:
                message = f"Connection was closed successfully."
                self.ui.ble_end_status_signal.emit(message)
                self.ui.ble_status_signal.emit(f"BLE disconnected", "red")
            else:
                self.ui.ble_end_status_signal.emit("Connection closing failed.")
        except asyncio.TimeoutError:
            self.ui.ble_end_status_signal.emit("Timeout occurred while trying to disconnect.")
        except Exception as e:
            self.ui.ble_end_status_signal.emit(f"An error occurred: {e}")
