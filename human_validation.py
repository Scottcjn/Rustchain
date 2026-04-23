import time

def verify_human_engagement():
    print("--- Rustchain Human Validation Protocol ---")
    print("Agent is performing sensitive operation.")
    print("Please confirm you are present by typing 'CONFIRM' below.")
    
    start_time = time.time()
    while time.time() - start_time < 300: # Ждем 5 минут
        user_input = input("Enter confirmation code: ")
        if user_input.strip().upper() == "CONFIRM":
            print("Validation successful. Human verified.")
            return True
        else:
            print("Invalid input. Try again.")
    return False

if __name__ == "__main__":
    verify_human_engagement()
