from postcodes_io_api import Api

api = Api()
data = api.get_postcode("SW11 2EF")
print(data)
