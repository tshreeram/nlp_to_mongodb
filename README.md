🧠 NLP-Driven MongoDB Query Assistant

Welcome to the **NLP-Driven MongoDB Query Assistant** — a smart tool that allows users to retrieve data from a MongoDB database by simply typing queries in **plain English**. No prior technical or database knowledge is required. Just type, click, and fetch!

🌟 Features

- 🗣️ Converts natural language into valid **MongoDB queries**
- 📊 Executes the query in the **backend** and fetches real data
- 🖥️ Displays both the **MongoDB query** and the **results** in a clean web interface
- 🧑‍💼 Designed for non-technical users — just plain English is enough!
- 💡 Helps beginners learn how MongoDB queries are structured

---

⚙️ Tech Stack

| Layer       | Tech Used            |
|-------------|----------------------|
| Backend     | Python, Flask        |
| NLP Engine  | NLTK                 |
| Database    | MongoDB              |
| Frontend    | HTML, CSS            |

---

🧪 Sample Usage

> User Input:  
> `Show all customers from Bangalore who registered after 2022`

> MongoDB Query Output:
```json
{
  "city": "Bangalore",
  "registration_date": { "$gt": ISODate("2022-01-01") }
}
