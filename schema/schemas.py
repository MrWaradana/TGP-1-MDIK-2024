def individual_serial(crime) -> dict:
    return {
        "id": str(crime.get("_id")),
        "ID": str(crime.get("ID", "")),
        "Case_Number": str(crime.get("Case Number", "")),
        "Date": str(crime.get("Date", "")),
        "Block": str(crime.get("Block", "")),
        "IUCR": str(crime.get("IUCR", "")),
        "Primary_Type": str(crime.get("Primary Type", "")),
        "Description": str(crime.get("Description", "")),
        "Location_Description": str(crime.get("Location Description", "")),
        "Arrest": str(crime.get("Arrest", "")),
        "Domestic": bool(crime.get("Domestic", False)),
        "Beat": str(crime.get("Beat", "")),
        "District": str(crime.get("District", "")),
        "Ward": str(crime.get("Ward", "")),
        "Community_Area": str(crime.get("Community Area", "")),
        "FBI_Code": str(crime.get("FBI Code", "")),
        "Year": str(crime.get("Year", "")),
        "Updated_On": str(crime.get("Updated On", "")),
    }


def list_serial(crimes) -> list:
    return [individual_serial(crime) for crime in crimes]
