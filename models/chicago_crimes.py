from pydantic import BaseModel
# from beanie


class Chicago_Crime(BaseModel):
    ID: str
    Case_Number: str
    Date: str
    Block: str
    IUCR: str
    Primary_Type: str
    Description: str
    Location_Description: str
    Arrest: str
    Domestic: bool
    Beat: str
    District: str
    Ward: str
    Community_Area: str
    FBI_Code: str
    Year: str
    Updated_On: str
