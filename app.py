from flask import Flask, render_template, request
from pymongo import MongoClient
import cohere

# Initialize the Flask application
app = Flask(__name__)

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017')  # Replace with your MongoDB URI
db = client['recipe']                      # Replace with your MongoDB database name
variants_collection = db['recipe_variants']        # Collection for recipe variants
instructions_collection = db['recipe_instruction'] # Collection for recipe instructions

# Initialize the Cohere client
cohere_client = cohere.Client('GWXBY4ukai4jOW2iW0BsiM6x8YQShoW230yAxn4a')  # Replace with your actual Cohere API key

# Home route to display the main search page
@app.route('/')
def index():
    return render_template('index.html')

# Route to search for recipe variants by name
@app.route('/search-recipe/<recipe_name>', methods=['GET'])
def search_recipe(recipe_name):
    # Search for the recipe variants based on the recipe name
    existing_variants = variants_collection.find_one({"name": {"$regex": recipe_name, "$options": "i"}})

    if existing_variants:
        # Collect all variants from the found document
        generated_variants = existing_variants.get('variants', [])
        generated_variants.append(existing_variants['name'])  # Include the main name (optional)
    else:
        generated_variants = []  # No variants found

        # If no variants are found, generate recipe instructions using Cohere
        instructions = generate_recipe_instructions(recipe_name)
        return render_template('result.html', recipes=[{'name': recipe_name, 'instructions': instructions}], error=None)

    # Render the search results page with the variants found
    return render_template('search_results.html', variants=generated_variants, keyword=recipe_name)

# Route to handle general search functionality (if needed for other queries)
@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')

    # Search for recipe variants that match the keyword (case-insensitive)
    existing_variants = list(variants_collection.find({"name": {"$regex": keyword, "$options": "i"}}))

    # Prepare a list to hold all variants if any matching documents are found
    if existing_variants:
        # Collect all variants from the found documents
        generated_variants = []
        for variant in existing_variants:
            generated_variants.extend(variant['variants'])  # Extend the list with variants from each found document
        generated_variants.append(existing_variants[0]['name'])  # Include the main name (optional)
    else:
        generated_variants = []  # No variants found

        # If no variants are found, generate recipe instructions using Cohere
        instructions = generate_recipe_instructions(keyword)
        return render_template('result.html', recipes=[{'name': keyword, 'instructions': instructions}], error=None)

    # Render the search results page
    return render_template('search_results.html', variants=generated_variants, keyword=keyword)

# Function to generate recipe instructions using Cohere
def generate_recipe_instructions(recipe_name):
    try:
        response = cohere_client.generate(
            model='command-xlarge',  # Ensure this model ID is valid and accessible
            prompt=f'Generate a recipe for {recipe_name}.',
            max_tokens=200,  # Adjust based on how detailed you want the recipe
            temperature=0.7
        )
        return response.generations[0].text.strip()
    except cohere.NotFoundError as e:
        # Handle the case where the model is not found
        return f"Error: {e.message}. Please check your model ID and access."
    except Exception as e:
        # Handle any other exceptions
        return f"An error occurred: {str(e)}"

# Route to display detailed instructions for a specific recipe variant
@app.route('/get-recipe/<title>', methods=['GET'])
def get_recipe(title):
    # Fetch the recipe instructions from MongoDB using the title
    instructions = instructions_collection.find_one({"name": title})

    if instructions:
        # If instructions are found, render them
        return render_template('result.html', recipes=[instructions])
    else:
        # If no instructions are found, generate using Cohere
        instructions = generate_recipe_instructions(title)
        return render_template('result.html', recipes=[{'name': title, 'instructions': instructions}], error=None)

# Route to combine previous recipe with new ingredients
@app.route('/combine-recipe', methods=['POST'])
def combine_recipe():
    previous_recipe_name = request.form.get('previous_recipe')
    new_ingredient = request.form.get('new_ingredient')

    # Retrieve the previous recipe's ingredients from the database
    previous_recipe = instructions_collection.find_one({"name": previous_recipe_name})
    previous_ingredients = previous_recipe['ingredients'] if previous_recipe else []

    # Combine previous ingredients with the new ingredient
    combined_ingredients = previous_ingredients + [new_ingredient]

    # Generate combined recipe instructions using Cohere
    combined_recipe_name = f"{previous_recipe_name} with {new_ingredient}"
    combined_instructions = generate_recipe_instructions(combined_recipe_name)

    # Prepare the combined recipe result
    combined_recipe = {
        'name': combined_recipe_name,
        'instructions': combined_instructions,
        'ingredients': combined_ingredients  # Now includes the new ingredient
    }

    # Store the combined recipe instructions in the MongoDB database
    instructions_collection.insert_one(combined_recipe)

    return render_template('result.html', recipes=[combined_recipe])

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
