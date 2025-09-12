"""
Website scraping service to extract salon services, pricing, and professional information
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .models import Location, Service

logger = logging.getLogger(__name__)

@dataclass
class ScrapedService:
    """Data structure for scraped service information"""
    name: str
    description: str
    price_text: str
    price_cents: Optional[int]
    duration_text: str
    duration_min: Optional[int]
    category: str
    professional_name: Optional[str] = None
    professional_bio: Optional[str] = None
    specialties: List[str] = None
    image_url: Optional[str] = None
    
    def __post_init__(self):
        if self.specialties is None:
            self.specialties = []

@dataclass
class ScrapedProfessional:
    """Data structure for scraped professional information"""
    name: str
    title: str
    bio: str
    specialties: List[str]
    experience_years: Optional[int] = None
    certifications: List[str] = None
    image_url: Optional[str] = None
    
    def __post_init__(self):
        if self.specialties is None:
            self.specialties = []
        if self.certifications is None:
            self.certifications = []

@dataclass
class ScrapedLocationInfo:
    """Complete scraped information for a location"""
    location_url: str
    business_name: str
    address: str
    phone: str
    hours: Dict[str, str]
    services: List[ScrapedService]
    professionals: List[ScrapedProfessional]
    faq_items: List[Dict[str, str]]
    scraped_at: datetime

class SalonWebsiteScraper:
    """Scraper for salon/beauty websites"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.service_keywords = {
            'haircut': ['haircut', 'cut', 'trim', 'shampoo cut', 'wash cut'],
            'color': ['color', 'coloring', 'highlights', 'lowlights', 'balayage', 'ombre', 'toner'],
            'styling': ['blowout', 'styling', 'updo', 'braids', 'curls', 'straightening'],
            'treatment': ['treatment', 'deep condition', 'keratin', 'protein', 'mask', 'repair'],
            'perm': ['perm', 'permanent wave', 'texture', 'wave'],
            'extensions': ['extensions', 'weave', 'clip-ins', 'tape-ins'],
            'makeup': ['makeup', 'cosmetics', 'beauty', 'facial'],
            'nails': ['manicure', 'pedicure', 'nails', 'gel', 'acrylic'],
            'waxing': ['wax', 'waxing', 'hair removal'],
            'facial': ['facial', 'skincare', 'cleansing', 'exfoliation']
        }
        
    async def __aenter__(self):
        import ssl
        # Create SSL context that doesn't verify certificates (for testing)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            connector=connector
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _extract_price(self, text: str) -> Optional[int]:
        """Extract price in cents from text"""
        if not text:
            return None
            
        # Look for price patterns like $50, $45.00, etc.
        price_patterns = [
            r'\$(\d+)\.(\d{2})',  # $45.00
            r'\$(\d+)',           # $45
            r'(\d+)\.(\d{2})',    # 45.00
            r'(\d+)\s*dollars?',  # 45 dollars
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text.lower())
            if match:
                if len(match.groups()) == 2:
                    dollars = int(match.group(1))
                    cents = int(match.group(2))
                    return dollars * 100 + cents
                else:
                    return int(match.group(1)) * 100
        
        return None
    
    def _extract_duration(self, text: str) -> Optional[int]:
        """Extract duration in minutes from text"""
        if not text:
            return None
            
        # Look for duration patterns
        duration_patterns = [
            r'(\d+)\s*hours?\s*(\d+)\s*min',  # 1 hour 30 min
            r'(\d+)\s*hrs?\s*(\d+)\s*min',    # 1 hr 30 min
            r'(\d+)\s*hours?',                # 2 hours
            r'(\d+)\s*hrs?',                  # 2 hrs
            r'(\d+)\s*min',                   # 45 min
            r'(\d+)\s*minutes?',              # 45 minutes
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, text.lower())
            if match:
                if 'hour' in pattern or 'hr' in pattern:
                    if len(match.groups()) == 2:
                        hours = int(match.group(1))
                        minutes = int(match.group(2))
                        return hours * 60 + minutes
                    else:
                        return int(match.group(1)) * 60
                else:
                    return int(match.group(1))
        
        return None
    
    def _categorize_service(self, name: str, description: str) -> str:
        """Categorize service based on keywords"""
        text = f"{name} {description}".lower()
        
        for category, keywords in self.service_keywords.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return 'other'
    
    async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return BeautifulSoup(html, 'html.parser')
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _extract_services_from_page(self, soup: BeautifulSoup, base_url: str) -> List[ScrapedService]:
        """Extract services from a webpage"""
        services = []
        
        # Common selectors for service information
        service_selectors = [
            '.service, .service-item, .menu-item',
            '.price-list-item, .pricing-item',
            '[class*="service"], [class*="menu"], [class*="price"]',
            'tr, .row'  # Table rows or grid items
        ]
        
        for selector in service_selectors:
            service_elements = soup.select(selector)
            
            for element in service_elements:
                text = element.get_text(strip=True)
                if len(text) < 10:  # Skip short elements
                    continue
                
                # Extract service name (usually in heading or strong text)
                name_elem = element.find(['h1', 'h2', 'h3', 'h4', 'strong', '.name', '.title'])
                if name_elem:
                    name = name_elem.get_text(strip=True)
                else:
                    # Fallback: use first line
                    lines = text.split('\n')
                    name = lines[0] if lines else text[:50]
                
                # Skip if name is too generic or short
                if len(name) < 3 or name.lower() in ['services', 'menu', 'pricing']:
                    continue
                
                description = text.replace(name, '').strip()
                price_text = text
                duration_text = text
                
                # Look for price in nearby elements
                price_elem = element.find(['span', 'div'], class_=re.compile(r'price|cost|rate'))
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                
                # Look for duration in nearby elements
                duration_elem = element.find(['span', 'div'], class_=re.compile(r'time|duration|length'))
                if duration_elem:
                    duration_text = duration_elem.get_text(strip=True)
                
                # Extract numerical values
                price_cents = self._extract_price(price_text)
                duration_min = self._extract_duration(duration_text)
                category = self._categorize_service(name, description)
                
                # Look for associated professional
                professional_elem = element.find(['span', 'div'], class_=re.compile(r'stylist|professional|staff'))
                professional_name = professional_elem.get_text(strip=True) if professional_elem else None
                
                service = ScrapedService(
                    name=name,
                    description=description[:500],  # Limit description length
                    price_text=price_text,
                    price_cents=price_cents,
                    duration_text=duration_text,
                    duration_min=duration_min,
                    category=category,
                    professional_name=professional_name
                )
                
                services.append(service)
        
        # Remove duplicates based on name similarity
        unique_services = []
        seen_names = set()
        
        for service in services:
            name_key = re.sub(r'[^\w\s]', '', service.name.lower()).strip()
            if name_key not in seen_names and len(name_key) > 2:
                seen_names.add(name_key)
                unique_services.append(service)
        
        return unique_services
    
    def _extract_professionals_from_page(self, soup: BeautifulSoup) -> List[ScrapedProfessional]:
        """Extract professional/staff information from a webpage"""
        professionals = []
        
        # Common selectors for staff information
        staff_selectors = [
            '.staff, .team-member, .stylist, .professional',
            '[class*="staff"], [class*="team"], [class*="stylist"]',
            '.bio, .profile'
        ]
        
        for selector in staff_selectors:
            staff_elements = soup.select(selector)
            
            for element in staff_elements:
                # Extract name
                name_elem = element.find(['h1', 'h2', 'h3', 'h4', '.name', '.title'])
                if not name_elem:
                    continue
                
                name = name_elem.get_text(strip=True)
                if len(name) < 2:
                    continue
                
                # Extract title/position
                title_elem = element.find(['span', 'div', 'p'], class_=re.compile(r'title|position|role'))
                title = title_elem.get_text(strip=True) if title_elem else 'Stylist'
                
                # Extract bio
                bio_elem = element.find(['p', 'div'], class_=re.compile(r'bio|description|about'))
                bio = bio_elem.get_text(strip=True) if bio_elem else ''
                
                # Extract specialties from bio or dedicated section
                specialties = []
                specialty_keywords = ['specialize', 'expert', 'focus', 'specialty', 'specialties']
                text = element.get_text().lower()
                
                for keyword in specialty_keywords:
                    if keyword in text:
                        # Extract text after the keyword
                        after_keyword = text.split(keyword, 1)[-1][:200]
                        # Look for service-related words
                        for category, keywords in self.service_keywords.items():
                            if any(kw in after_keyword for kw in keywords):
                                specialties.append(category)
                
                professional = ScrapedProfessional(
                    name=name,
                    title=title,
                    bio=bio[:1000],  # Limit bio length
                    specialties=list(set(specialties))  # Remove duplicates
                )
                
                professionals.append(professional)
        
        return professionals
    
    def _extract_faq_from_page(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract FAQ items from a webpage"""
        faq_items = []
        
        # Look for FAQ sections
        faq_selectors = [
            '.faq, .faq-item, .question',
            '[class*="faq"], [class*="question"]',
            'details, .accordion-item'
        ]
        
        for selector in faq_selectors:
            faq_elements = soup.select(selector)
            
            for element in faq_elements:
                # Extract question
                question_elem = element.find(['h1', 'h2', 'h3', 'h4', 'summary', '.question', '.q'])
                if not question_elem:
                    continue
                
                question = question_elem.get_text(strip=True)
                if len(question) < 5:
                    continue
                
                # Extract answer
                answer_elem = element.find(['.answer', '.a', 'p', 'div'])
                if answer_elem:
                    answer = answer_elem.get_text(strip=True)
                else:
                    # Fallback: use remaining text
                    answer = element.get_text(strip=True).replace(question, '').strip()
                
                if len(answer) > 10:
                    faq_items.append({
                        'question': question,
                        'answer': answer[:1000]  # Limit answer length
                    })
        
        return faq_items
    
    async def scrape_salon_website(self, base_url: str) -> ScrapedLocationInfo:
        """Scrape a salon website for all relevant information"""
        logger.info(f"Starting scrape of {base_url}")
        
        # First try to extract JSON data from GlossGenius websites
        json_data = await self._extract_json_data(base_url)
        if json_data:
            return self._parse_glossgenius_data(json_data, base_url)
        
        # Fallback to traditional HTML scraping
        return await self._scrape_html_pages(base_url)
    
    async def _extract_json_data(self, base_url: str) -> Optional[Dict]:
        """Extract JSON data from GlossGenius or similar React-based websites"""
        try:
            soup = await self._fetch_page(base_url)
            if not soup:
                return None
            
            # Look for script tags with JSON data
            scripts = soup.find_all('script')
            
            for script in scripts:
                if not script.string:
                    continue
                
                # Try to find JSON data in various formats
                try:
                    # Try direct JSON object (starts with {)
                    if script.string.strip().startswith('{'):
                        json_data = json.loads(script.string)
                        if 'props' in json_data and 'serverContext' in json_data.get('props', {}):
                            logger.info("Found GlossGenius JSON data")
                            return json_data
                    
                    # Try __NEXT_DATA__ format
                    json_match = re.search(r'__NEXT_DATA__\s*=\s*({.*?});', script.string)
                    if json_match:
                        json_str = json_match.group(1)
                        json_data = json.loads(json_str)
                        if 'props' in json_data:
                            logger.info("Found Next.js JSON data")
                            return json_data
                            
                except json.JSONDecodeError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting JSON data: {e}")
            return None
    
    def _parse_glossgenius_data(self, json_data: Dict, base_url: str) -> ScrapedLocationInfo:
        """Parse GlossGenius JSON data to extract salon information"""
        services = []
        professionals = []
        business_name = ''
        address = ''
        phone = ''
        
        try:
            # Extract business information
            if 'props' in json_data and 'serverContext' in json_data['props']:
                server_context = json_data['props']['serverContext']
                
                if 'publicUser' in server_context:
                    public_user = server_context['publicUser']
                    business_name = public_user.get('business_name', '')
                    address = public_user.get('business_address', '')
                    phone = public_user.get('business_phone', '')
                
                # Extract services from users (users can be in publicUser or directly in serverContext)
                users_data = None
                if 'users' in public_user:
                    users_data = public_user['users']
                elif 'users' in server_context:
                    users_data = server_context['users']
                
                if users_data:
                    for user in users_data:
                        if 'services' in user and user['services']:
                            for service_data in user['services']:
                                service = self._parse_glossgenius_service(service_data, user.get('full_name', ''))
                                if service:
                                    services.append(service)
                        
                        # Extract professional information
                        if 'full_name' in user and user['full_name']:
                            professional = self._parse_glossgenius_professional(user)
                            if professional:
                                professionals.append(professional)
            
            # Remove duplicates
            unique_services = self._remove_duplicate_services(services)
            unique_professionals = self._remove_duplicate_professionals(professionals)
            
            return ScrapedLocationInfo(
                location_url=base_url,
                business_name=business_name or urlparse(base_url).netloc,
                address=address,
                phone=phone,
                hours={},
                services=unique_services,
                professionals=unique_professionals,
                faq_items=[],  # FAQ not typically in JSON data
                scraped_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error parsing GlossGenius data: {e}")
            # Return empty data on error
            return ScrapedLocationInfo(
                location_url=base_url,
                business_name=urlparse(base_url).netloc,
                address='',
                phone='',
                hours={},
                services=[],
                professionals=[],
                faq_items=[],
                scraped_at=datetime.now()
            )
    
    def _parse_glossgenius_service(self, service_data: Dict, professional_name: str = '') -> Optional[ScrapedService]:
        """Parse a single service from GlossGenius JSON data"""
        try:
            name = service_data.get('name', '').strip()
            if not name:
                return None
            
            price_str = service_data.get('price', '0.00')
            try:
                price_cents = int(float(price_str) * 100)
            except (ValueError, TypeError):
                price_cents = None
            
            duration_min = service_data.get('start_duration', 0)
            if duration_min == 0:
                duration_min = None
            
            # Create description from available data
            description_parts = []
            if professional_name:
                description_parts.append(f"Offered by {professional_name}")
            
            description = ' '.join(description_parts)
            
            return ScrapedService(
                name=name,
                description=description,
                price_text=f"${price_str}" if price_str != '0.00' else "Price varies",
                price_cents=price_cents,
                duration_text=f"{duration_min} min" if duration_min else "Duration varies",
                duration_min=duration_min,
                category=self._categorize_service(name, description),
                professional_name=professional_name if professional_name else None
            )
            
        except Exception as e:
            logger.error(f"Error parsing service data: {e}")
            return None
    
    def _parse_glossgenius_professional(self, user_data: Dict) -> Optional[ScrapedProfessional]:
        """Parse professional information from GlossGenius JSON data"""
        try:
            name = user_data.get('full_name', '').strip()
            if not name:
                return None
            
            # Extract specialties from services
            specialties = []
            if 'services' in user_data and user_data['services']:
                for service in user_data['services']:
                    service_name = service.get('name', '')
                    if service_name:
                        category = self._categorize_service(service_name, '')
                        if category != 'other' and category not in specialties:
                            specialties.append(category)
            
            # Create bio from available information
            bio_parts = []
            if user_data.get('instagram_url'):
                bio_parts.append(f"Instagram: {user_data['instagram_url']}")
            if user_data.get('phone'):
                bio_parts.append(f"Phone: {user_data['phone']}")
            
            bio = ' | '.join(bio_parts)
            
            return ScrapedProfessional(
                name=name,
                title='Stylist',  # Default title
                bio=bio,
                specialties=specialties
            )
            
        except Exception as e:
            logger.error(f"Error parsing professional data: {e}")
            return None
    
    async def _scrape_html_pages(self, base_url: str) -> ScrapedLocationInfo:
        """Fallback method to scrape HTML pages when JSON data is not available"""
        # Pages to check for different types of content
        pages_to_check = [
            '',  # Homepage
            '/services', '/menu', '/pricing', '/treatments',
            '/staff', '/team', '/stylists', '/professionals',
            '/about', '/faq', '/contact'
        ]
        
        all_services = []
        all_professionals = []
        all_faq_items = []
        business_name = ''
        address = ''
        phone = ''
        hours = {}
        
        for page_path in pages_to_check:
            url = urljoin(base_url, page_path)
            soup = await self._fetch_page(url)
            
            if not soup:
                continue
            
            # Extract business info from any page
            if not business_name:
                title_elem = soup.find('title')
                if title_elem:
                    business_name = title_elem.get_text(strip=True)
            
            if not phone:
                phone_elem = soup.find(text=re.compile(r'\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4}'))
                if phone_elem:
                    phone = phone_elem.strip()
            
            # Extract services
            page_services = self._extract_services_from_page(soup, base_url)
            all_services.extend(page_services)
            
            # Extract professionals
            page_professionals = self._extract_professionals_from_page(soup)
            all_professionals.extend(page_professionals)
            
            # Extract FAQ
            page_faq = self._extract_faq_from_page(soup)
            all_faq_items.extend(page_faq)
            
            # Small delay between requests
            await asyncio.sleep(0.5)
        
        # Remove duplicates
        unique_services = self._remove_duplicate_services(all_services)
        unique_professionals = self._remove_duplicate_professionals(all_professionals)
        unique_faq = self._remove_duplicate_faq(all_faq_items)
        
        return ScrapedLocationInfo(
            location_url=base_url,
            business_name=business_name or urlparse(base_url).netloc,
            address=address,
            phone=phone,
            hours=hours,
            services=unique_services,
            professionals=unique_professionals,
            faq_items=unique_faq,
            scraped_at=datetime.now()
        )
    
    def _remove_duplicate_services(self, services: List[ScrapedService]) -> List[ScrapedService]:
        """Remove duplicate services based on name similarity"""
        unique_services = []
        seen_names = set()
        
        for service in services:
            name_key = re.sub(r'[^\w\s]', '', service.name.lower()).strip()
            if name_key not in seen_names and len(name_key) > 2:
                seen_names.add(name_key)
                unique_services.append(service)
        
        return unique_services
    
    def _remove_duplicate_professionals(self, professionals: List[ScrapedProfessional]) -> List[ScrapedProfessional]:
        """Remove duplicate professionals based on name"""
        unique_professionals = []
        seen_names = set()
        
        for professional in professionals:
            name_key = professional.name.lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique_professionals.append(professional)
        
        return unique_professionals
    
    def _remove_duplicate_faq(self, faq_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove duplicate FAQ items based on question similarity"""
        unique_faq = []
        seen_questions = set()
        
        for item in faq_items:
            question_key = re.sub(r'[^\w\s]', '', item['question'].lower()).strip()
            if question_key not in seen_questions and len(question_key) > 5:
                seen_questions.add(question_key)
                unique_faq.append(item)
        
        return unique_faq

async def update_location_from_website(location_id: int, website_url: str) -> Dict[str, Any]:
    """Scrape website and update location services in database"""
    from .database import initialize_database
    
    async with SalonWebsiteScraper() as scraper:
        scraped_info = await scraper.scrape_salon_website(website_url)
        
        # Initialize database and save scraped data
        db_manager = initialize_database()
        async with db_manager.get_session() as session:
            # Update existing services or create new ones
            updated_services = []
            
            for scraped_service in scraped_info.services:
                # Check if service already exists
                result = await session.execute(
                    select(Service).where(
                        and_(
                            Service.location_id == location_id,
                            Service.name.ilike(f"%{scraped_service.name}%")
                        )
                    )
                )
                existing_service = result.scalar_one_or_none()
                
                if existing_service:
                    # Update existing service
                    if scraped_service.price_cents:
                        existing_service.price_cents = scraped_service.price_cents
                    if scraped_service.duration_min:
                        existing_service.duration_min = scraped_service.duration_min
                    existing_service.notes = f"Updated from website: {scraped_service.description}"
                    updated_services.append(existing_service)
                else:
                    # Create new service
                    new_service = Service(
                        location_id=location_id,
                        name=scraped_service.name,
                        duration_min=scraped_service.duration_min or 60,  # Default 1 hour
                        price_cents=scraped_service.price_cents or 0,
                        active_bool=True,
                        notes=f"Scraped from website: {scraped_service.description}"
                    )
                    session.add(new_service)
                    updated_services.append(new_service)
            
            await session.commit()
        
        # Save complete scraped data to JSON file for AI reference
        scraped_data_file = f"scraped_data_location_{location_id}.json"
        scraped_data = {
            'location_id': location_id,
            'scraped_at': scraped_info.scraped_at.isoformat(),
            'business_info': {
                'name': scraped_info.business_name,
                'url': scraped_info.location_url,
                'phone': scraped_info.phone,
                'address': scraped_info.address,
                'hours': scraped_info.hours
            },
            'services': [asdict(service) for service in scraped_info.services],
            'professionals': [asdict(professional) for professional in scraped_info.professionals],
            'faq': scraped_info.faq_items
        }
        
        with open(scraped_data_file, 'w') as f:
            json.dump(scraped_data, f, indent=2, default=str)
        
        logger.info(f"Scraped {len(scraped_info.services)} services, {len(scraped_info.professionals)} professionals, {len(scraped_info.faq_items)} FAQ items for location {location_id}")
        
        return {
            'status': 'success',
            'services_count': len(scraped_info.services),
            'professionals_count': len(scraped_info.professionals),
            'faq_count': len(scraped_info.faq_items),
            'data_file': scraped_data_file
        }
