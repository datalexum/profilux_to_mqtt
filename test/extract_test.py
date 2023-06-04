import re
import unittest

from src.main import construct_mqtt_topic_and_message, extract_data_from_content


def parse_string(input_string):
    result = []

    # Split string by newline characters and iterate through each line
    for line in input_string.split('\n'):
        # Use regex to match the pattern in the line
        match = re.match(r'\s*([\w-]+)\s*([0-9]*):\s*([\d.]+)(\w*)', line)
        if match:
            data_dict = {
                "Type": match.group(1),  # Extract type
                "Index": match.group(2) if match.group(2) else None,  # Extract index
                "Value": match.group(3),  # Extract value
                "Unit": match.group(4)  # Extract unit
            }
            result.append(data_dict)

    return result


class MyTestCase(unittest.TestCase):
    def test_extract_data_from_content(self):
        test_email_content = """
        Temperatur 1 : 25.5C
        pH-Wert 1 : 7.94pH
        KH Director : 8.0dKH
        """

        expected_output = [
            {
                "Type": "Temperatur",
                "Index": "1",
                "Value": "25.5",
                "Unit": "C",
            },
            {
                "Type": "pH-Wert",
                "Index": "1",
                "Value": "7.94",
                "Unit": "pH",
            },
            {
                "Type": "KH Director",
                "Index": None,
                "Value": "8.0",
                "Unit": "dKH",
            },
        ]

        actual_output = parse_string(test_email_content)
        self.assertEqual(actual_output, expected_output)

    def test_construct_mqtt_topic_and_message(self):
        test_data = {
            "Type": "Temperatur",
            "Index": "1",
            "Value": "25.5",
            "Unit": "C",
        }

        test_email_date = "Tue, 25 May 2023 16:00:00 +0000"
        expected_topic = "/profilux_mqtt/temperatur/1"
        expected_message = {
            "value": 25.5,
            "date_time": test_email_date,
            "unit": "C",
        }

        actual_topic, actual_message = construct_mqtt_topic_and_message(test_data, test_email_date)

        self.assertEqual(actual_topic, expected_topic)
        self.assertEqual(actual_message, expected_message)


if __name__ == '__main__':
    unittest.main()
