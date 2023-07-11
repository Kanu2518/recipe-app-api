"""
Tests for recipe apis.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe , Tag , Ingredient
from recipe.serializers import RecipeSerializer , RecipeDetailSerializer

RECIPE_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Create and return a recipe detail url."""
    return reverse('recipe:recipe-detail',args=[recipe_id])

def create_recipe(user,**params):
    """Create and return example recipe."""
    defaults = {
        'title':'Sample recipe title',
        'time_minutes':22,
        'price':Decimal('5.25'),
        'description':'Sample description',
        'link':'http://exaple.com/recipe.pdf',
    }
    defaults.update(params)

    recipe = Recipe.objects.create(user=user,**defaults)
    return recipe

def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)

# For unauthenticated users tests.
class PublicRecipeAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()
    
    # TEST 24
    def test_auth_required(self):
        """Test auth required to call API."""
        res = self.client.get(RECIPE_URL)

        self.assertEqual(res.status_code,status.HTTP_401_UNAUTHORIZED)
    

# For authenticated users tests.
class PrivateRecipeAPITests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email='example@gmail.com',password='pass123')
        self.client.force_authenticate(user=self.user)

    # Recipe Test
    def test_retrieve_recipe(self):
        """Test retrieving a list of recipes."""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes,many=True)

        self.assertEqual(res.status_code,status.HTTP_200_OK)
        self.assertEqual(res.data,serializer.data)
    
    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is authenticated user."""
        other_user = create_user(
            email='other@gmail.com',
            password='password123',
        )
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes,many=True)

        self.assertEqual(res.status_code,status.HTTP_200_OK)
        self.assertEqual(res.data,serializer.data)
    
    def test_get_recipe_detail(self):
        """Test get recipe details."""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data,serializer.data)
    
    def test_create_recipe(self):
        """Test creating a recipe."""
        payload = {
            'title':'Sample recipe',
            'time_minutes':30,
            'price':Decimal('5.50'),
        }
        res = self.client.post(RECIPE_URL,payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=res.data['id'])
        for k,v in payload.items():
            self.assertEqual(getattr(recipe,k),v)
        self.assertEqual(recipe.user,self.user)

    def test_partial_update(self):
        """Test partial update of a recipe."""
        original_link = 'https://example.com/recipe.pdf'
        recipe = create_recipe(
            user=self.user,
            title='Sample recipe title',
            link=original_link
        )
        payload = {'title':'New recipe title'}
        url = detail_url(recipe.id)
        res = self.client.patch(url,payload)

        self.assertEqual(res.status_code,status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title,payload['title'])
        self.assertEqual(recipe.link,original_link)
        self.assertEqual(recipe.user,self.user)
    
    def test_full_update(self):
        """Test full update of a recipe."""
        recipe = create_recipe(
            user=self.user,
            title='Sample recipe title',
            link='https://example.com/recipe.pdf'
        )

        payload = {
            'title':'New recipe title',
            'link':'https://example.com/new-recipe.pdf',
            'description':'New description for recipe',
            'price':Decimal('5.50'),
            'time_minutes':20
        }

        url = detail_url(recipe.id)
        res = self.client.put(url,payload)
        self.assertEqual(res.status_code,status.HTTP_200_OK)

        recipe.refresh_from_db()

        for k,v in payload.items():
            self.assertEqual(getattr(recipe,k),v)
        
        self.assertEqual(recipe.user,self.user)

    def test_update_user_return_error(self):
        """Test changing the recipe user results in an error."""
        new_user = create_user(email='user2@gmail.com',password='test123')
        recipe = create_recipe(user=self.user)

        payload = {'user':new_user}
        url = detail_url(recipe.id)
        self.client.patch(url,payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.user,self.user)

    def test_delete_recipe(self):
        """Test delete recipe successfully."""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code,status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_delete_other_user_recipes_error(self):
        """Test trying to delete other users recipe given error."""
        new_user = create_user(email='user2@gmail.com',password='pass456')
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code,status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())
    
    # Recipe add Tags test
    def test_create_recipe_with_new_tags(self):
        """Test create a recipe with tags."""
        payload={
            'title': 'Thai Prawn Curry',
            'time_minutes': 30,
            'price': Decimal('2.50'),
            'tags': [{'name':'Thai'},{'name':'Dinner'}]
        }
        res = self.client.post(RECIPE_URL,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(),1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(),2)
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exists)
    
    def test_create_recipe_with_exist_tags(self):
        """Test create a recipe with existing tag."""
        tag_indian = Tag.objects.create(user=self.user,name='Indian')
        payload = {
            'title':'Pongal',
            'time_minutes':60,
            'price':Decimal('4.50'),
            'tags':[{'name':'Indian'},{'name':'BreakFats'}]
        }
        res = self.client.post(RECIPE_URL,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(),1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(),2)
        self.assertIn(tag_indian,recipe.tags.all())
        
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)
    
    def test_create_tag_on_update(self):
        """Test creating tag when updating a recipe."""
        recipe = create_recipe(user=self.user)
        
        payload = {'tags':[{'name':'Lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_200_OK)

        new_tag = Tag.objects.get(user=self.user,name='Lunch')
        self.assertIn(new_tag,recipe.tags.all())
    
    def test_update_recipe_assign_tag(self):
        """Test assigning an existing tag when updating a recipe."""
        tag_breakfast = Tag.objects.create(user=self.user,name='BreakFast')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user,name='Lunch')
        payload = {'tags':[{'name':'Lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_200_OK)
        self.assertIn(tag_lunch,recipe.tags.all())
        self.assertNotIn(tag_breakfast,recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clearing a recipes tags."""
        tag = Tag.objects.create(user=self.user,name='Dessert')
        recipe = create_recipe(user=self.user)

        payload = {'tags':[]}
        url = detail_url(recipe.id)
        res = self.client.patch(url,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(),0)

    # Recipe add Ingredients test 
    def test_create_recipe_with_new_ingredients(self):
        """Test create recipe with ingredients."""
        payload = {
            'title': 'Cauliflower Tacos',
            'time_minutes': 60,
            'price': Decimal('4.30'),
            'ingredients': [{'name': 'Cauliflower'}, {'name': 'Salt'}],
        }
        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_exist_ingredient(self):
        """Test create recipe with ingredients."""
        ingredient_fruit = Ingredient.objects.create(user=self.user,name='Mango')
        payload = {
            'title': 'Cauliflower Tacos',
            'time_minutes': 60,
            'price': Decimal('4.30'),
            'ingredients': [{'name': 'Mango'}, {'name': 'Strawberry'}],
        }
        res = self.client.post(RECIPE_URL,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(),1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(),2)
        self.assertIn(ingredient_fruit,recipe.ingredients.all())

        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exists)
    
    def test_create_ingredient_update(self):
        """Test creating ingredient when updating a recipe."""
        recipe = create_recipe(user=self.user)

        payload = {'ingredients':[{'name':'Lemon'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_200_OK)

        new_ingredient = Ingredient.objects.get(user=self.user,name='Lemon')
        self.assertIn(new_ingredient,recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assigning an existing ingredient when updating a recipe."""
        ingredient_tomato = Ingredient.objects.create(user=self.user,name='Tomato')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient_tomato)

        ingredient_onion = Ingredient.objects.create(user=self.user,name='Onion')
        payload = {'ingredients':[{'name':'Onion'}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url,payload,format='json')


        self.assertEqual(res.status_code,status.HTTP_200_OK)
        self.assertIn(ingredient_onion,recipe.ingredients.all())
        self.assertNotIn(ingredient_tomato,recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        """Test clearing a recipes ingredients."""
        ingredient = Ingredient.objects.create(user=self.user,name='Banana')
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        payload = {'ingredients': []}
        res = self.client.patch(url,payload,format='json')

        self.assertEqual(res.status_code,status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(),0)