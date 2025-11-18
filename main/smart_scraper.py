"""
Smart Incremental Scraper
Scraper ที่ฉลาดขึ้น - จะ scrape เฉพาะ URL ที่ยังไม่มี content
"""

import pandas as pd
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import sys
import os

# เพิ่ม path สำหรับ import modules
sys.path.append(str(Path(__file__).parent))

# Import scraper module
import importlib.util
spec = importlib.util.spec_from_file_location("news_scraper", "news_scraper_1.2.py")
news_scraper_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news_scraper_module)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartIncrementalScraper:
    """
    Smart Scraper ที่จะ scrape เฉพาะ URL ที่ยังไม่มี content
    """

    def __init__(self):
        # สร้าง scraper instance
        self.scraper = news_scraper_module

    def check_content_status(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        แยก URLs ที่มี content แล้วกับที่ยังไม่มี

        Returns:
            tuple: (urls_with_content, urls_need_scraping)
        """
        # URLs ที่มี content แล้ว (ไม่ว่าง และไม่ใช่ NaN)
        has_content = df[
            df['content'].notna() &
            (df['content'] != '') &
            (df['content'] != 'None') &
            (df['content'].str.len() > 10)  # มีเนื้อหาอย่างน้อย 10 ตัวอักษร
        ].copy()

        # URLs ที่ต้อง scrape ใหม่
        need_scraping = df[
            df['content'].isna() |
            (df['content'] == '') |
            (df['content'] == 'None') |
            (df['content'].str.len() <= 10)
        ].copy()

        logger.info(f"URLs ที่มี content แล้ว: {len(has_content)}")
        logger.info(f"URLs ที่ต้อง scrape: {len(need_scraping)}")

        return has_content, need_scraping

    async def scrape_missing_content(self, df_to_scrape: pd.DataFrame) -> pd.DataFrame:
        """
        Scrape เฉพาะ URLs ที่ยังไม่มี content
        """
        if len(df_to_scrape) == 0:
            logger.info("ไม่มี URL ที่ต้อง scrape")
            return df_to_scrape

        logger.info(f"เริ่ม scrape {len(df_to_scrape)} URLs")

        try:
            # Scrape URLs ใหม่
            scraped_df = await self.scraper.scrape_all_async(df_to_scrape)

            logger.info(f"Scraping เสร็จ - ได้ผลลัพธ์ {len(scraped_df)} รายการ")

            return scraped_df

        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการ scrape: {e}")
            # ถ้า scrape ล้มเหลว ให้ส่งคืนข้อมูลเดิม
            return df_to_scrape

    async def process_prepare_data(self, input_file: str, output_file: str = None) -> pd.DataFrame:
        """
        ประมวลผล prepare_data.csv แบบ incremental

        Args:
            input_file: path ไปยัง prepare_data.csv
            output_file: path สำหรับบันทึกผลลัพธ์ (ถ้าไม่ระบุจะใช้ชื่อเดิม)
        """
        logger.info(f"อ่านข้อมูลจาก: {input_file}")

        # อ่านข้อมูล
        df = pd.read_csv(input_file)
        logger.info(f"พบข้อมูล {len(df)} รายการ")

        # ตรวจสอบ columns ที่จำเป็น
        required_columns = ['url']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"ไม่พบ columns ที่จำเป็น: {missing_columns}")

        # เพิ่ม columns ที่ขาดหาย
        if 'content' not in df.columns:
            df['content'] = ''
        if 'scrape_status' not in df.columns:
            df['scrape_status'] = ''

        # แยก URLs ที่มี content แล้วกับที่ยังไม่มี
        has_content_df, need_scraping_df = self.check_content_status(df)

        # Scrape เฉพาะที่ยังไม่มี content
        if len(need_scraping_df) > 0:
            newly_scraped_df = await self.scrape_missing_content(need_scraping_df)

            # รวมข้อมูลที่มี content แล้วกับที่ scrape ใหม่
            final_df = pd.concat([has_content_df, newly_scraped_df], ignore_index=True)
        else:
            final_df = has_content_df.copy()

        # เรียงลำดับตาม URL เพื่อให้ผลลัพธ์สม่ำเสมอ
        final_df = final_df.sort_values('url').reset_index(drop=True)

        # บันทึกผลลัพธ์
        if output_file is None:
            output_file = input_file  # เขียนทับไฟล์เดิม

        final_df.to_csv(output_file, index=False, encoding='utf-8')
        logger.info(f"บันทึกผลลัพธ์ไปที่: {output_file}")

        # สรุปผลลัพธ์
        summary = {
            'total_urls': len(final_df),
            'already_had_content': len(has_content_df),
            'newly_scraped': len(need_scraping_df),
            'successful_scrapes': len(final_df[final_df['scrape_status'] == 'success']),
            'failed_scrapes': len(final_df[final_df['scrape_status'] == 'failed'])
        }

        logger.info("=== สรุปผลการ Scraping ===")
        for key, value in summary.items():
            logger.info(f"{key}: {value}")

        return final_df

def create_sample_prepare_data(output_file: str = "prepare_data.csv"):
    """
    สร้างไฟล์ prepare_data.csv ตัวอย่าง (มี content บางส่วน)
    """
    sample_data = {
        'url': [
            'https://www.thairath.co.th/news/local/2567890',
            'https://www.dailynews.co.th/news/5025690/',
            'https://www.bangkokpost.com/thailand/general/2567891',
            'https://www.khaosod.co.th/breaking-news/news_4567892',
            'https://www.matichon.co.th/local/news_3456789'
        ],
        'context': [
            'ข่าวท้องถิ่น',
            'ข่าวต่างประเทศ',
            'ข่าวทั่วไป',
            'ข่าวด่วน',
            'ข่าวท้องถิ่น'
        ],
        'content': [
            '',  # ยังไม่มี content - ต้อง scrape
            'สำนักข่าวเอเอฟพี รายงานจากเมืองการาจี ประเทศปากีสถาน...',  # มี content แล้ว
            '',  # ยังไม่มี content - ต้อง scrape
            'None',  # content ว่าง - ต้อง scrape ใหม่
            'เกิดเหตุการณ์...'  # มี content แล้ว
        ],
        'scrape_status': [
            '',
            'success',
            '',
            'failed',
            'success'
        ]
    }

    df = pd.DataFrame(sample_data)
    df.to_csv(output_file, index=False, encoding='utf-8')
    logger.info(f"สร้างไฟล์ตัวอย่าง: {output_file}")
    return df

async def main():
    """
    ฟังก์ชันหลักสำหรับทดสอบ Smart Scraper
    """
    import argparse

    parser = argparse.ArgumentParser(description='Smart Incremental Scraper')
    parser.add_argument('--input', default='prepare_data.csv', help='Input prepare_data.csv file')
    parser.add_argument('--output', help='Output file (default: same as input)')
    parser.add_argument('--create-sample', action='store_true', help='Create sample prepare_data.csv')

    args = parser.parse_args()

    # สร้างไฟล์ตัวอย่างถ้าต้องการ
    if args.create_sample:
        create_sample_prepare_data(args.input)
        logger.info(f"สร้างไฟล์ตัวอย่าง {args.input} เสร็จแล้ว")
        return

    # ตรวจสอบว่าไฟล์ input มีอยู่หรือไม่
    if not Path(args.input).exists():
        logger.error(f"ไม่พบไฟล์: {args.input}")
        logger.info("ใช้ --create-sample เพื่อสร้างไฟล์ตัวอย่าง")
        sys.exit(1)

    # สร้าง Smart Scraper และประมวลผล
    scraper = SmartIncrementalScraper()

    try:
        result_df = await scraper.process_prepare_data(args.input, args.output)
        logger.info("Smart Scraping เสร็จสิ้น!")

    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาด: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())