
class Repository:
    
    def __init__(self):
        self.__options = {}
        self.__modules = []
    
    def require_option(self, name, description):
        self.__options[name] = description
    
    def __setitem__(self, key, value):
        print(key, value)
    
    def __getitem__(self, key):
        print(key)
    
    def appendModule(self, module):
        self.__modules.append(module)
    
    def getModules(self):
        return self.__modules
