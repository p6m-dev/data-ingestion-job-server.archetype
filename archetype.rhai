let context = #{};

// Pass `-s debug-answers` to archetect to output the answers it sees from various sources
if switch_enabled("debug-answers") {
    print("Answers:");
    print(as_yaml(ANSWERS));
    print();
}


// Pass `-s debug-context` to archetect to output the context
if switch_enabled("debug-context") {
    print("Context:");
    print(as_yaml(context));
    print();
}

render(Directory("contents/base"), context);
context