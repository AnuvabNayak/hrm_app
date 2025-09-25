from services.timezone_utils import *

# Test current functionality
print("🧪 Testing Timezone Utilities")
print("=" * 50)

# Test current time
utc_time = utc_now()
ist_time = ist_now()
print(f"UTC Now: {utc_time}")
print(f"IST Now: {ist_time}")

# Test conversion
converted = utc_to_ist(utc_time)
print(f"UTC to IST: {converted}")

# Test formatting
print(f"IST DateTime: {format_ist_datetime(utc_time)}")
print(f"IST Date: {format_ist_date(utc_time)}")
print(f"IST Time 12h: {format_ist_time_12h(utc_time)}")
print(f"IST Time 24h: {format_ist_time_24h(utc_time)}")

# Test debug
print("\n🔍 Debug Info:")
debug_info = debug_timezone_info(utc_time)
for key, value in debug_info.items():
    print(f"  {key}: {value}")

print("\n✅ Timezone utilities created successfully!")
