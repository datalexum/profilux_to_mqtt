import logging
import os
import re
import json
import time
import imaplib
import email

from dotenv import load_dotenv
from paho.mqtt import client as mqtt_client
from azure.storage.blob import BlobServiceClient

load_dotenv()
logging.getLogger().setLevel(logging.DEBUG)

# Constants
SERVICE_NAME = os.getenv("SERVICE_NAME")
IMAP_SERVER = os.getenv("IMAP_SERVER")  # your IMAP server
IMAP_USER = os.getenv("IMAP_USER")  # your IMAP username
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")  # your IMAP password
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")  # your Azure connection string
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")  # your Azure container name for logs
MQTT_BROKER = os.getenv("MQTT_BROKER")  # your MQTT broker address
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))  # your MQTT broker port
MQTT_USERNAME = os.getenv("MQTT_USERNAME")  # your MQTT username
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")  # your MQTT password

type_map = {
    "pH-Wert": "pH",
    "KH Director": "KH"
}

# Setting up IMAP client
mail = imaplib.IMAP4_SSL(IMAP_SERVER)
mail.login(IMAP_USER, IMAP_PASSWORD)

# Setting up MQTT client
mqtt_client = mqtt_client.Client("profilux_mqtt_service")
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Setting up Azure Blob Storage client
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)


def extract_data_from_content(content):
    result = []

    # Split string by newline characters and iterate through each line
    for line in content.split('\n'):
        # Use regex to match the pattern in the line
        match = re.match(r'\s*([\w\s-]+)\s*([0-9]*)\s*:\s*([\d.]+)(\w*)', line)
        if match:
            type_index = match.group(1).rstrip()  # Extract type and index string
            # Separate the type and index
            type_str, index_str = re.match(r'([^\d]*)(\d*)', type_index).groups()
            data_dict = {
                "Type": type_map.get(type_str.rstrip(), type_str.rstrip()),  # Remove trailing spaces from type
                "Index": int(index_str) if index_str else None,  # Extract index
                "Value": float(match.group(3)),  # Extract value
                "Unit": match.group(4)  # Extract unit
            }
            result.append(data_dict)

    return result


def construct_mqtt_topic_and_message(data, email_date):
    topic = f"/{SERVICE_NAME}/{data.get('Type').lower()}"
    if data.get('Index'):
        topic += f"/{data.get('Index')}"
    if data.get('Subtype'):
        topic += f"/{data.get('Subtype').lower()}"
    message = {
        "value": float(data.get('Value')),
        "date_time": email_date,
        "unit": data.get('Unit') if data.get('Unit') else "",
    }
    return topic, message


def process_email(email_id):
    result, email_data = mail.uid('fetch', email_id, '(BODY.PEEK[])')
    raw_email = email_data[0][1].decode('utf-8')
    email_message = email.message_from_string(raw_email)
    if email_message['subject'] == 'Profilux-Value':
        email_date = email_message['Date']
        if email_message.is_multipart():
            for payload in email_message.get_payload():
                content = payload.get_payload(decode=True)
        else:
            content = email_message.get_payload(decode=True)

        data_list = extract_data_from_content(content.decode("utf-8"))
        produced_messages = {}
        for data in data_list:
            topic, message = construct_mqtt_topic_and_message(data, email_date)
            mqtt_client.publish(topic, json.dumps(message))

            print(f"Produced to {topic}: {message['value']}")

            produced_messages[topic] = message

        blob_client = blob_service_client.get_blob_client(AZURE_CONTAINER_NAME, f"{int(time.time())}.txt")
        blob_client.upload_blob(json.dumps(produced_messages))
        print(f"Messages saved as blob {blob_client.blob_name}")


def main():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    while True:
        mail.select("inbox")
        result, data = mail.uid('search', None, "ALL")

        for email_id in data[0].split():
            process_email(email_id)

            # Delete processed email
            mail.uid('STORE', email_id, '+FLAGS', '(\Deleted)')
        mail.expunge()

        # Wait for a while before checking the inbox again
        time.sleep(60)


if __name__ == "__main__":
    main()
