#!/usr/bin/env python3
"""
Human-Like Behavior Module for Form Automation

Simulates natural human interaction patterns to avoid bot detection:
- Variable typing speeds with occasional typos
- Natural mouse movements with Bezier curves
- Random micro-pauses and scrolling
- Field-to-field timing delays
"""

import asyncio
import random
import math
from typing import Optional, Tuple, List


class HumanBehavior:
    """Simulates human-like interaction patterns for browser automation."""
    
    # Typing speed range (milliseconds per character)
    MIN_TYPING_DELAY = 80
    MAX_TYPING_DELAY = 150
    
    # Typo probability (10% of fields will have a typo that gets corrected)
    TYPO_PROBABILITY = 0.10
    
    # Field timing delays (seconds)
    FIELD_DELAYS = {
        'name': (0.5, 1.5),
        'email': (0.8, 2.0),
        'phone': (1.0, 2.5),
        'company': (0.5, 1.5),
        'subject': (0.5, 1.5),
        'message': (3.0, 8.0),
        'submit': (1.0, 3.0),
        'default': (0.5, 1.5),
    }
    
    # Adjacent keys for realistic typos
    ADJACENT_KEYS = {
        'a': 'sqwz', 'b': 'vghn', 'c': 'xdfv', 'd': 'serfcx', 'e': 'wrsdf',
        'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'i': 'ujklo', 'j': 'huikmn',
        'k': 'jiolm', 'l': 'kop', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp',
        'p': 'ol', 'q': 'wa', 'r': 'edft', 's': 'awedxz', 't': 'rfgy',
        'u': 'yhji', 'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu', 'z': 'asx',
        '1': '2q', '2': '13qw', '3': '24we', '4': '35er', '5': '46rt',
        '6': '57ty', '7': '68yu', '8': '79ui', '9': '80io', '0': '9p',
    }
    
    def __init__(self, typo_enabled: bool = True, speed_variance: float = 0.3):
        """
        Initialize human behavior simulator.
        
        Args:
            typo_enabled: Whether to introduce and correct typos
            speed_variance: How much typing speed varies (0-1)
        """
        self.typo_enabled = typo_enabled
        self.speed_variance = speed_variance
        
    def get_typing_delay(self) -> int:
        """Get random typing delay in milliseconds."""
        base = random.randint(self.MIN_TYPING_DELAY, self.MAX_TYPING_DELAY)
        variance = int(base * self.speed_variance * random.uniform(-1, 1))
        return max(40, base + variance)  # Never faster than 40ms
    
    def should_make_typo(self) -> bool:
        """Determine if a typo should be made."""
        return self.typo_enabled and random.random() < self.TYPO_PROBABILITY
    
    def get_typo_char(self, intended_char: str) -> str:
        """Get a realistic typo for a character (adjacent key)."""
        lower = intended_char.lower()
        if lower in self.ADJACENT_KEYS:
            adjacent = self.ADJACENT_KEYS[lower]
            typo = random.choice(adjacent)
            # Preserve case
            return typo.upper() if intended_char.isupper() else typo
        return intended_char  # No typo if no adjacent keys
    
    def get_field_delay(self, field_type: str) -> float:
        """Get delay before interacting with a field type."""
        delay_range = self.FIELD_DELAYS.get(field_type.lower(), self.FIELD_DELAYS['default'])
        return random.uniform(*delay_range)
    
    def bezier_point(self, t: float, p0: Tuple[float, float], p1: Tuple[float, float],
                     p2: Tuple[float, float], p3: Tuple[float, float]) -> Tuple[float, float]:
        """Calculate point on cubic Bezier curve at parameter t."""
        x = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
        return (x, y)
    
    def generate_mouse_path(self, start: Tuple[float, float], end: Tuple[float, float],
                           steps: int = 20) -> List[Tuple[float, float]]:
        """
        Generate natural mouse movement path using Bezier curves.
        
        Args:
            start: Starting (x, y) position
            end: Ending (x, y) position
            steps: Number of points in the path
            
        Returns:
            List of (x, y) coordinates for mouse movement
        """
        # Generate random control points for natural curve
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        
        # Control point offsets (perpendicular to movement direction)
        offset_range = max(abs(dx), abs(dy)) * 0.3
        
        p1 = (
            start[0] + dx * 0.3 + random.uniform(-offset_range, offset_range),
            start[1] + dy * 0.3 + random.uniform(-offset_range, offset_range)
        )
        p2 = (
            start[0] + dx * 0.7 + random.uniform(-offset_range, offset_range),
            start[1] + dy * 0.7 + random.uniform(-offset_range, offset_range)
        )
        
        # Generate path points
        path = []
        for i in range(steps + 1):
            t = i / steps
            point = self.bezier_point(t, start, p1, p2, end)
            path.append(point)
        
        return path
    
    def get_click_offset(self, width: float, height: float) -> Tuple[float, float]:
        """
        Get random offset within element bounds (not dead center).
        
        Args:
            width: Element width
            height: Element height
            
        Returns:
            (x_offset, y_offset) from element top-left
        """
        # Click somewhere in the middle 60% of the element
        margin_x = width * 0.2
        margin_y = height * 0.2
        
        x = random.uniform(margin_x, width - margin_x)
        y = random.uniform(margin_y, height - margin_y)
        
        return (x, y)
    
    def get_scroll_pattern(self, target_y: float, viewport_height: float) -> List[int]:
        """
        Generate natural scroll pattern to reach target position.
        
        Args:
            target_y: Target Y position to scroll to
            viewport_height: Browser viewport height
            
        Returns:
            List of scroll amounts (can be multiple scrolls)
        """
        scrolls = []
        current = 0
        
        while current < target_y - viewport_height * 0.7:
            # Variable scroll amount (100-400 pixels typically)
            scroll_amount = random.randint(100, 400)
            scrolls.append(scroll_amount)
            current += scroll_amount
        
        return scrolls
    
    async def type_with_human_behavior(self, page, selector: str, text: str,
                                        clear_first: bool = True) -> None:
        """
        Type text into a field with human-like behavior.
        
        Args:
            page: Playwright page object
            selector: CSS selector for the input field
            text: Text to type
            clear_first: Whether to clear the field first
        """
        # Check if it's a select element
        element = await page.query_selector(selector)
        if element:
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            if tag_name == 'select':
                # Handle dropdown - skip typing, just select first or best option
                await self._handle_select(page, selector, text)
                return
        
        # Click the field first
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        # Clear if needed
        if clear_first:
            await page.fill(selector, '')
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Decide if this field will have a typo
        make_typo = self.should_make_typo()
        typo_index = random.randint(3, max(3, len(text) - 3)) if make_typo else -1
        
        # Type character by character
        for i, char in enumerate(text):
            # Insert typo and correction
            if i == typo_index:
                typo_char = self.get_typo_char(char)
                await page.type(selector, typo_char, delay=self.get_typing_delay())
                await asyncio.sleep(random.uniform(0.1, 0.3))  # Realize mistake
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Type the actual character
            await page.type(selector, char, delay=self.get_typing_delay())
        
        # Post-typing pause
        await asyncio.sleep(random.uniform(0.3, 0.8))
    
    async def _handle_select(self, page, selector: str, value: str) -> None:
        """Handle a select/dropdown element."""
        # Get available options
        options = await page.evaluate(f'''() => {{
            const select = document.querySelector('{selector}');
            if (!select) return [];
            return Array.from(select.options).map(o => ({{
                value: o.value,
                text: o.text.toLowerCase()
            }}));
        }}''')
        
        if not options:
            return
        
        # Try to find a matching option
        value_lower = value.lower()
        
        # First: exact match
        for opt in options:
            if opt['text'] == value_lower or opt['value'].lower() == value_lower:
                await page.select_option(selector, opt['value'])
                return
        
        # Second: partial match
        for opt in options:
            if value_lower in opt['text'] or opt['text'] in value_lower:
                await page.select_option(selector, opt['value'])
                return
        
        # Third: prefer generic options like "general", "inquiry", "other"
        preferred = ['general', 'inquiry', 'question', 'other', 'sales', 'product', 'information']
        for pref in preferred:
            for opt in options:
                if pref in opt['text']:
                    await page.select_option(selector, opt['value'])
                    return
        
        # Fallback: select first non-empty option
        for opt in options:
            if opt['value'] and opt['text'] and opt['text'] != 'select':
                await page.select_option(selector, opt['value'])
                return
    
    async def human_click(self, page, selector: str) -> None:
        """
        Click an element with natural mouse movement.
        
        Args:
            page: Playwright page object
            selector: CSS selector for the element to click
        """
        element = await page.query_selector(selector)
        if not element:
            raise ValueError(f"Element not found: {selector}")
        
        box = await element.bounding_box()
        if not box:
            raise ValueError(f"Element has no bounding box: {selector}")
        
        # Get random point within element
        offset_x, offset_y = self.get_click_offset(box['width'], box['height'])
        target_x = box['x'] + offset_x
        target_y = box['y'] + offset_y
        
        # Get current mouse position (approximate from viewport center)
        viewport = page.viewport_size
        start_x = viewport['width'] / 2 + random.uniform(-100, 100)
        start_y = viewport['height'] / 2 + random.uniform(-100, 100)
        
        # Generate and follow mouse path
        path = self.generate_mouse_path((start_x, start_y), (target_x, target_y))
        
        for point in path:
            await page.mouse.move(point[0], point[1])
            await asyncio.sleep(random.uniform(0.01, 0.03))
        
        # Small pause before click
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Click
        await page.mouse.click(target_x, target_y)
    
    async def human_scroll(self, page, amount: Optional[int] = None) -> None:
        """
        Scroll the page naturally.
        
        Args:
            page: Playwright page object
            amount: Total scroll amount (random if not specified)
        """
        if amount is None:
            amount = random.randint(150, 400)
        
        # Scroll in small increments
        increments = random.randint(3, 8)
        per_increment = amount / increments
        
        for _ in range(increments):
            await page.mouse.wheel(0, per_increment)
            await asyncio.sleep(random.uniform(0.02, 0.08))
        
        # Pause to "read"
        await asyncio.sleep(random.uniform(0.5, 2.0))
    
    async def wait_like_human(self, page, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """
        Wait/pause like a human would.
        
        Args:
            page: Playwright page object (not used but kept for API consistency)
            min_sec: Minimum wait time
            max_sec: Maximum wait time
        """
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def prepare_for_form(self, page) -> None:
        """
        Perform natural page entry behavior before form interaction.
        
        Args:
            page: Playwright page object
        """
        # Wait for page to feel "ready"
        await self.wait_like_human(page, 1.0, 2.5)
        
        # Maybe scroll a bit to "find" the form
        if random.random() < 0.7:  # 70% chance to scroll
            await self.human_scroll(page)


# Convenience functions for simpler usage
_default_behavior = HumanBehavior()

async def human_type(page, selector: str, text: str, clear_first: bool = True):
    """Convenience function for human-like typing."""
    await _default_behavior.type_with_human_behavior(page, selector, text, clear_first)

async def human_click(page, selector: str):
    """Convenience function for human-like clicking."""
    await _default_behavior.human_click(page, selector)

async def human_scroll(page, amount: Optional[int] = None):
    """Convenience function for human-like scrolling."""
    await _default_behavior.human_scroll(page, amount)

async def human_wait(page, min_sec: float = 1.0, max_sec: float = 3.0):
    """Convenience function for human-like waiting."""
    await _default_behavior.wait_like_human(page, min_sec, max_sec)


if __name__ == "__main__":
    # Quick test of behavior generation
    behavior = HumanBehavior()
    
    print("Testing mouse path generation...")
    path = behavior.generate_mouse_path((0, 0), (500, 300))
    print(f"Generated {len(path)} points")
    print(f"Start: {path[0]}, End: {path[-1]}")
    
    print("\nTesting typing delays...")
    for _ in range(5):
        print(f"Delay: {behavior.get_typing_delay()}ms")
    
    print("\nTesting field delays...")
    for field in ['name', 'email', 'message', 'submit']:
        print(f"{field}: {behavior.get_field_delay(field):.2f}s")
    
    print("\nTesting typo generation...")
    for char in 'abcde':
        print(f"'{char}' -> typo: '{behavior.get_typo_char(char)}'")
