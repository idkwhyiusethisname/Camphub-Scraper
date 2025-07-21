# 🎓 Camphub-Scraper

> ระบบดึงข้อมูลค่ายจากเว็บไซต์ [Camphub](https://www.camphub.in.th) พร้อมระบบแจ้งเตือนผ่าน Discord Webhook แบบอัตโนมัติ

![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)
![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)
![Auto Notify](https://img.shields.io/badge/Discord-Webhook%20Notify-7289da.svg)
![GitHub Repo stars](https://img.shields.io/github/stars/idkwhyiusethisname/Camphub-Scraper?style=social)


---

## ❓ ทำไมถึงทำโปรเจกต์นี้

หลายครั้งเจอปัญหาที่ "ค่ายหมดเวลาสมัครแล้ว" เพราะ **ลืมเข้าไปดู** หรือ **ไม่รู้ว่ามีค่ายเปิดใหม่** เลยเกิดไอเดียนี้ขึ้น

---

## 🛠️ ฟีเจอร์หลักที่ระบบนี้ทำได้

- 🔎 ดึงข้อมูลค่ายจาก Camphub ตาม:
  - หมวดหมู่
  - แท็ก เช่น #แพทย์ #มหาวิทยาลัย
  - มหาวิทยาลัยเอกชน/รัฐบาล
- 📅 ดึงข้อมูลรายละเอียดครบ:
  - ชื่อค่าย
  - วันเปิด/ปิดรับสมัคร
  - ค่าใช้จ่าย
  - ผู้จัดกิจกรรม
  - ลิงก์ค่าย
- 🔔 แจ้งเตือนผ่าน **Discord Webhook**
  - เมื่อพบค่ายใหม่
  - หรือค่ายที่ยังไม่มีในฐานข้อมูล
  - (Cornjob เอานะ)
- 🎯 กรองการแจ้งเตือนได้ตามหมวดหมู่ที่สนใจ

---
## 📍 Roadmap

- [ ] รองรับการแจ้งเตือนผ่าน **Telegram Bot**
- [ ] ใช้งานผ่าน **Docker**
- [ ] ระบบแจ้งเตือน **ข่าวสารทั่วไป** ที่เกี่ยวข้องกับการศึกษา/ค่าย
- [ ] แจ้งเตือนเมื่อค่าย **ใกล้หมดเขตรับสมัคร**
- [ ] Public api
- [ ] MultiThread

---

## 📜 License

**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**  

- ✅ ใช้, แก้ไข, แชร์ ได้ **เพื่อการไม่พาณิชย์เท่านั้น**
- ✅ ต้องให้เครดิตเจ้าของผลงาน

📄 ดูรายละเอียดเพิ่มเติมได้ที่ [LICENSE](./LICENSE) หรือที่  
🔗 [creativecommons.org/licenses/by-nc/4.0](https://creativecommons.org/licenses/by-nc/4.0/)

---

## 📬 ติดต่อหรือแจ้งปัญหา

ถ้าพบปัญหา / อยากให้ระบบเพิ่มฟีเจอร์อะไรใหม่ ๆ  
สามารถเปิด Issue หรือ Pull Request มาได้เลยนะครับ 🙌

---

> Make with ❤️ (ขอโทษคับที่ pirate api มันไม่มี public api ให้ผมช้ายยย)
